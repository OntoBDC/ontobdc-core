from pathlib import Path
from typing import Any, Dict, List, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment.error import (
    ContainerAttachError,
    DatasetAttachError,
    StorageIndexAttachError,
)
from ontobdc.storage.adapter.attachment.graph import (
    AttachmentGraphNamespaceBootstrap,
    AttachmentGraphOperations,
)
from ontobdc.storage.adapter.attachment.plan import (
    AttachmentPlanConstants,
    AttachmentPlanner,
)
from ontobdc.storage.adapter.attachment.transaction import (
    AttachmentTransactionCoordinator,
)

AttachmentGraphNamespaceBootstrap.initialize()
_CT = AttachmentGraphNamespaceBootstrap.CT
_OBDC = AttachmentGraphNamespaceBootstrap.OBDC


class AttachmentMetadataService:
    """Apply the resolved attachment plan to container / storage graphs.

    This is the core mutating service of the attachment pipeline:

    * Reads the previously resolved plan from the CLI context (via
      ``AttachmentPlanner.require_resolved_plan``), guaranteeing that
      ``inspect_container`` and ``resolve_identity`` ran before any graph
      mutation happens.
    * Rewrites the container graph (remapping URIs from the export-side
      identities into their on-disk counterparts via
      ``AttachmentPlanner.uri_mapping``) and rewrites each dataset graph
      individually.
    * Adds or updates the resulting ``DataContainer`` in the storage index
      while refusing to attach a container whose identity or location
      collides with a *different* pre-existing storage entry.
    * Optionally rewrites ``belongsToDataContainer`` cross-references
      between dataset and container graph so the rewritten container
      subject is used consistently.
    * Runs every write through ``AttachmentTransactionCoordinator`` so
      failure is atomic — either every graph file is updated together, or
      the backup created at plan-resolution time is restored.
    """

    def __init__(
        self,
        context: CliContextPort,
        *,
        plan_parameter: str = AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
        completed_parameter: str = AttachmentPlanConstants.ATTACH_COMPLETED_PARAMETER,
        error_parameter: str = AttachmentPlanConstants.ATTACH_ERROR_PARAMETER,
    ) -> None:
        self._context: CliContextPort = context
        self._plan_parameter: str = plan_parameter
        self._completed_parameter: str = completed_parameter
        self._error_parameter: str = error_parameter

    def attach_container_metadata(self) -> Dict[str, Any]:
        context: CliContextPort = self._context
        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context,
            plan_parameter=self._plan_parameter,
        ).require_resolved_plan()
        container_file: Path = Path(attachment_plan["container_file"])
        container_graph: Graph = AttachmentGraphOperations.load_graph(
            container_file,
            ContainerAttachError,
        )
        source_container_subject: URIRef = URIRef(
            attachment_plan["source_container_subject"]
        )
        target_container_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        target_container_id: str = attachment_plan["target_container_id"]
        target_container_location: str = attachment_plan["target_container_location"]
        mapping: Dict[URIRef, URIRef] = AttachmentPlanner.uri_mapping(attachment_plan)
        rewritten_container: Graph = AttachmentGraphOperations.rewrite_graph(
            container_graph,
            mapping,
        )
        AttachmentGraphOperations.set_single(
            rewritten_container,
            target_container_subject,
            DCTERMS.identifier,
            Literal(target_container_id),
        )
        AttachmentGraphOperations.set_single(
            rewritten_container,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )

        self._attach_datasets_core(attachment_plan, mapping, rewritten_container)

        storage_file: Path = Path(attachment_plan["storage_file"])
        storage_graph: Graph = AttachmentGraphOperations.load_graph(
            storage_file,
            StorageIndexAttachError,
        )
        self._prune_conflicting_container_nodes(
            storage_graph=storage_graph,
            attachment_plan=attachment_plan,
        )
        title: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            DCTERMS.title,
            ContainerAttachError,
            "container title",
        )
        description: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            _CT.description,
            ContainerAttachError,
            "container description",
        )
        creation_date: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            _CT.creationDate,
            ContainerAttachError,
            "container creation date",
        )
        storage_graph.add(
            (target_container_subject, RDF.type, _OBDC.DataContainer)
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            DCTERMS.title,
            title,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            _CT.description,
            description,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            _CT.creationDate,
            creation_date,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            DCTERMS.identifier,
            Literal(target_container_id),
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )
        self._attach_storage_index_core(rewritten_container, storage_graph)

        payloads: Dict[Path, Graph] = {
            container_file: rewritten_container,
            storage_file: storage_graph,
        }
        for dataset in attachment_plan["datasets"]:
            payloads[Path(dataset["file"])] = dataset["_rewritten_graph"]

        AttachmentTransactionCoordinator(
            context,
            attachment_plan,
            self._plan_parameter,
        ).ensure_backup()
        try:
            AttachmentTransactionCoordinator.write_graphs_transactionally(payloads)
        except Exception as error:
            AttachmentTransactionCoordinator(
                context,
                attachment_plan,
                self._plan_parameter,
            ).restore()
            context.set_parameter_value(self._error_parameter, str(error))
            raise ContainerAttachError(
                f"Attachment failed and backup was restored: {error}"
            ) from error
        AttachmentTransactionCoordinator(
            context=None,  # type: ignore[arg-type]
            plan=attachment_plan,
            plan_parameter="",
        ).discard_backup()
        context.set_parameter_value(self._completed_parameter, True)
        context.delete_parameter(self._error_parameter)
        return {
            "container_file": str(container_file),
            "storage_file": str(storage_file),
            "dataset_count": len(attachment_plan["datasets"]),
        }

    def is_container_metadata_attached(self) -> bool:
        completed: Any = self._context.get_parameter_value(
            self._completed_parameter
        )
        return bool(completed)

    @classmethod
    def _attach_datasets_core(
        cls,
        attachment_plan: Dict[str, Any],
        mapping: Dict[URIRef, URIRef],
        rewritten_container: Graph,
    ) -> List[Dict[str, Any]]:
        rewrites: List[Dict[str, Any]] = []
        target_container_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        for dataset in attachment_plan["datasets"]:
            dataset_file: Path = Path(dataset["file"])
            dataset_graph: Graph = AttachmentGraphOperations.load_graph(
                dataset_file,
                DatasetAttachError,
            )
            rewritten: Graph = AttachmentGraphOperations.rewrite_graph(
                dataset_graph,
                mapping,
            )
            dataset_subject: URIRef = AttachmentGraphOperations.single_subject(
                rewritten,
                RDF.type,
                _OBDC.EntityDataset,
                DatasetAttachError,
                "dataset",
            )
            AttachmentGraphOperations.set_single(
                rewritten,
                dataset_subject,
                DCTERMS.identifier,
                Literal(dataset["target_id"]),
            )
            AttachmentGraphOperations.set_single(
                rewritten,
                dataset_subject,
                PROV.atLocation,
                dataset["target_location"],
            )
            AttachmentGraphOperations.set_single(
                rewritten,
                dataset_subject,
                _OBDC.belongsToDataContainer,
                target_container_subject,
            )
            rewritten_container.add(
                (target_container_subject, _OBDC.hasDataset, dataset_subject)
            )
            dataset["_rewritten_graph"] = rewritten
            rewrites.append(dataset)
        return rewrites

    @classmethod
    def _is_datasets_attached_core(
        cls,
        attachment_plan: Dict[str, Any],
        rewritten_container: Graph,
    ) -> bool:
        target_container_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        expected: set[str] = {
            dataset["target_subject"]
            for dataset in attachment_plan["datasets"]
        }
        actual: set[str] = {
            str(dataset_subject)
            for dataset_subject in rewritten_container.objects(
                target_container_subject,
                _OBDC.hasDataset,
            )
        }
        return expected.issubset(actual)

    @classmethod
    def _attach_storage_index_core(
        cls,
        rewritten_container: Graph,
        storage_graph: Graph,
    ) -> List[URIRef]:
        target_container_subject: URIRef = AttachmentGraphOperations.single_subject(
            rewritten_container,
            RDF.type,
            _OBDC.DataContainer,
            ContainerAttachError,
            "container",
        )
        dataset_subjects: List[URIRef] = sorted(
            {
                subject
                for subject in storage_graph.subjects(
                    _OBDC.belongsToDataContainer, target_container_subject
                )
                if isinstance(subject, URIRef)
            }
        )
        for subject in dataset_subjects:
            storage_graph.add((subject, RDF.type, _OBDC.EntityDataset))
            identifier: Any = next(
                iter(rewritten_container.objects(subject, DCTERMS.identifier)),
                None,
            )
            location: Any = next(
                iter(rewritten_container.objects(subject, PROV.atLocation)),
                None,
            )
            if identifier is not None:
                AttachmentGraphOperations.set_single(
                    storage_graph,
                    subject,
                    DCTERMS.identifier,
                    identifier,
                )
            if location is not None:
                AttachmentGraphOperations.set_single(
                    storage_graph,
                    subject,
                    PROV.atLocation,
                    location,
                )
        storage_graph.add(
            (target_container_subject, RDF.type, _OBDC.DataContainer)
        )
        return dataset_subjects

    @classmethod
    def _is_storage_index_attached_core(
        cls,
        rewritten_container: Graph,
        storage_graph: Graph,
    ) -> bool:
        target_container_subject: URIRef = AttachmentGraphOperations.single_subject(
            rewritten_container,
            RDF.type,
            _OBDC.DataContainer,
            ContainerAttachError,
            "container",
        )
        target_container_id: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            DCTERMS.identifier,
            ContainerAttachError,
            "container identifier",
        )
        target_container_triple: Tuple[URIRef, URIRef, URIRef] = (
            URIRef(target_container_id),
            RDF.type,
            _OBDC.DataContainer,
        )
        if target_container_triple not in storage_graph:
            return False
        return True

    @classmethod
    def _prune_conflicting_container_nodes(
        cls,
        *,
        storage_graph: Graph,
        attachment_plan: Dict[str, Any],
    ) -> None:
        duplicates: List[URIRef] = AttachmentGraphOperations.matching_container_subjects(
            storage_graph,
            source_subject=URIRef(attachment_plan["source_container_subject"]),
            target_subject=URIRef(attachment_plan["target_container_subject"]),
            source_id=attachment_plan["source_container_id"],
            target_id=attachment_plan["target_container_id"],
            source_location=attachment_plan["source_container_location"],
            target_location=attachment_plan["target_container_location"],
        )
        for subject in duplicates:
            AttachmentGraphOperations.remove_subject(storage_graph, subject)

    @classmethod
    def _build_rewritten_container(
        cls,
        attachment_plan: Dict[str, Any],
    ) -> Graph:
        container_file: Path = Path(attachment_plan["container_file"])
        container_graph: Graph = AttachmentGraphOperations.load_graph(
            container_file,
            ContainerAttachError,
        )
        target_container_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        target_container_id: str = attachment_plan["target_container_id"]
        target_container_location: str = attachment_plan["target_container_location"]
        mapping: Dict[URIRef, URIRef] = AttachmentPlanner.uri_mapping(attachment_plan)
        rewritten_container: Graph = AttachmentGraphOperations.rewrite_graph(
            container_graph,
            mapping,
        )
        AttachmentGraphOperations.set_single(
            rewritten_container,
            target_container_subject,
            DCTERMS.identifier,
            Literal(target_container_id),
        )
        AttachmentGraphOperations.set_single(
            rewritten_container,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )
        return rewritten_container

    @classmethod
    def attach_datasets(
        cls,
        context: CliContextPort,
        *,
        plan_parameter: str = AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
        completed_parameter: str = AttachmentPlanConstants.DATASETS_ATTACHED_COMPLETED_PARAMETER
        if hasattr(AttachmentPlanConstants, "DATASETS_ATTACHED_COMPLETED_PARAMETER")
        else AttachmentPlanConstants.ATTACH_COMPLETED_PARAMETER,
        error_parameter: str = AttachmentPlanConstants.ATTACH_ERROR_PARAMETER,
    ) -> Dict[str, Any]:
        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).require_resolved_plan()
        mapping: Dict[URIRef, URIRef] = AttachmentPlanner.uri_mapping(attachment_plan)
        rewritten_container: Graph = cls._build_rewritten_container(attachment_plan)
        if cls._is_datasets_attached_core(attachment_plan, rewritten_container):
            return {
                "container_file": str(attachment_plan["container_file"]),
                "dataset_count": len(attachment_plan["datasets"]),
            }
        dataset_rewrites: List[Dict[str, Any]] = cls._attach_datasets_core(
            attachment_plan,
            mapping,
            rewritten_container,
        )
        payloads: Dict[Path, Graph] = {
            Path(attachment_plan["container_file"]): rewritten_container,
        }
        for dataset in dataset_rewrites:
            payloads[Path(dataset["file"])] = dataset["_rewritten_graph"]
        AttachmentTransactionCoordinator(
            context,
            attachment_plan,
            plan_parameter,
        ).ensure_backup()
        try:
            AttachmentTransactionCoordinator.write_graphs_transactionally(payloads)
        except Exception as error:
            AttachmentTransactionCoordinator(
                context,
                attachment_plan,
                plan_parameter,
            ).restore()
            context.set_parameter_value(error_parameter, str(error))
            raise DatasetAttachError(
                f"Datasets attachment failed and backup was restored: {error}"
            ) from error
        AttachmentTransactionCoordinator(
            context=None,  # type: ignore[arg-type]
            plan=attachment_plan,
            plan_parameter="",
        ).discard_backup()
        context.set_parameter_value(completed_parameter, True)
        context.delete_parameter(error_parameter)
        return {
            "container_file": str(attachment_plan["container_file"]),
            "dataset_count": len(attachment_plan["datasets"]),
        }

    @classmethod
    def is_datasets_attached(
        cls,
        context: CliContextPort,
        *,
        plan_parameter: str = AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
    ) -> bool:
        if not AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).is_identity_resolved():
            return False
        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).require_resolved_plan()
        rewritten_container: Graph = cls._build_rewritten_container(attachment_plan)
        return cls._is_datasets_attached_core(attachment_plan, rewritten_container)

    @classmethod
    def attach_storage_index(
        cls,
        context: CliContextPort,
        *,
        plan_parameter: str = AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
        completed_parameter: str = AttachmentPlanConstants.STORAGE_INDEX_ATTACHED_COMPLETED_PARAMETER
        if hasattr(AttachmentPlanConstants, "STORAGE_INDEX_ATTACHED_COMPLETED_PARAMETER")
        else AttachmentPlanConstants.ATTACH_COMPLETED_PARAMETER,
        error_parameter: str = AttachmentPlanConstants.ATTACH_ERROR_PARAMETER,
    ) -> Dict[str, Any]:
        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).require_resolved_plan()
        rewritten_container: Graph = cls._build_rewritten_container(attachment_plan)
        storage_file: Path = Path(attachment_plan["storage_file"])
        storage_graph: Graph = AttachmentGraphOperations.load_graph(
            storage_file,
            StorageIndexAttachError,
        )
        if cls._is_storage_index_attached_core(rewritten_container, storage_graph):
            return {
                "storage_file": str(storage_file),
            }
        cls._prune_conflicting_container_nodes(
            storage_graph=storage_graph,
            attachment_plan=attachment_plan,
        )
        target_container_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        title: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            DCTERMS.title,
            StorageIndexAttachError,
            "container title",
        )
        description: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            _CT.description,
            StorageIndexAttachError,
            "container description",
        )
        creation_date: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            _CT.creationDate,
            StorageIndexAttachError,
            "container creation date",
        )
        target_container_id: str = attachment_plan["target_container_id"]
        target_container_location: str = attachment_plan["target_container_location"]
        storage_graph.add((target_container_subject, RDF.type, _OBDC.DataContainer))
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            DCTERMS.title,
            title,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            _CT.description,
            description,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            _CT.creationDate,
            creation_date,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            DCTERMS.identifier,
            Literal(target_container_id),
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )
        cls._attach_storage_index_core(rewritten_container, storage_graph)
        payloads: Dict[Path, Graph] = {
            storage_file: storage_graph,
        }
        AttachmentTransactionCoordinator(
            context,
            attachment_plan,
            plan_parameter,
        ).ensure_backup()
        try:
            AttachmentTransactionCoordinator.write_graphs_transactionally(payloads)
        except Exception as error:
            AttachmentTransactionCoordinator(
                context,
                attachment_plan,
                plan_parameter,
            ).restore()
            context.set_parameter_value(error_parameter, str(error))
            raise StorageIndexAttachError(
                f"Storage index attachment failed and backup was restored: {error}"
            ) from error
        AttachmentTransactionCoordinator(
            context=None,  # type: ignore[arg-type]
            plan=attachment_plan,
            plan_parameter="",
        ).discard_backup()
        context.set_parameter_value(completed_parameter, True)
        context.delete_parameter(error_parameter)
        return {
            "storage_file": str(storage_file),
        }

    @classmethod
    def is_storage_index_attached(
        cls,
        context: CliContextPort,
        *,
        plan_parameter: str = AttachmentPlanConstants.ATTACH_PLAN_PARAMETER,
    ) -> bool:
        if not AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).is_identity_resolved():
            return False
        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context,
            plan_parameter=plan_parameter,
        ).require_resolved_plan()
        rewritten_container: Graph = cls._build_rewritten_container(attachment_plan)
        storage_file: Path = Path(attachment_plan["storage_file"])
        if not storage_file.is_file():
            return False
        storage_graph: Graph = AttachmentGraphOperations.load_graph(
            storage_file,
            StorageIndexAttachError,
        )
        return cls._is_storage_index_attached_core(rewritten_container, storage_graph)
