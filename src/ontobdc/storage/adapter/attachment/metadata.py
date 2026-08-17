from pathlib import Path
from typing import Any, Dict, List

from rdflib import Graph, URIRef
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
            target_container_id,
        )
        AttachmentGraphOperations.set_single(
            rewritten_container,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )

        self.attach_datasets(attachment_plan, mapping, rewritten_container)

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
            _OBDC.description,
            ContainerAttachError,
            "container description",
        )
        creation_date: str = AttachmentGraphOperations.required_literal(
            rewritten_container,
            target_container_subject,
            _OBDC.creationDate,
            ContainerAttachError,
            "container creation date",
        )
        storage_graph.add(
            (target_container_subject, RDF.type, _OBDC.DataContainer)
        )
        storage_graph.add(
            (
                target_container_subject,
                DCTERMS.title,
                title,
            )
        )
        storage_graph.add(
            (
                target_container_subject,
                _OBDC.description,
                description,
            )
        )
        storage_graph.add(
            (
                target_container_subject,
                _OBDC.creationDate,
                creation_date,
            )
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            DCTERMS.identifier,
            target_container_id,
        )
        AttachmentGraphOperations.set_single(
            storage_graph,
            target_container_subject,
            PROV.atLocation,
            target_container_location,
        )
        self.attach_storage_index(rewritten_container, storage_graph)

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
    def attach_datasets(
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
                dataset["target_id"],
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
    def is_datasets_attached(
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
    def attach_storage_index(
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
    def is_storage_index_attached(
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
        target_container_id: str = AttachmentGraphOperations.required_uri(
            rewritten_container,
            target_container_subject,
            DCTERMS.identifier,
            ContainerAttachError,
            "container identifier",
        )
        if not storage_graph.contains(
            (URIRef(target_container_id), RDF.type, _OBDC.DataContainer)
        ):
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
