import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment.error import (
    DatasetAttachError,
    IdentityConflictError,
    InvalidContainerGraphError,
    InvalidContainerPathError,
    StorageIndexAttachError,
)
from ontobdc.storage.adapter.attachment.graph import (
    AttachmentGraphNamespaceBootstrap,
    AttachmentGraphOperations,
)
from ontobdc.storage.adapter.attachment.transaction import (
    AttachmentTransactionCoordinator,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

AttachmentGraphNamespaceBootstrap.initialize()
_CT = AttachmentGraphNamespaceBootstrap.CT
_OBDC = AttachmentGraphNamespaceBootstrap.OBDC


class AttachmentPlanConstants:
    """Module-wide parameter-name constants for the attachment planner.

    Keeping these names centralized on a dedicated class — instead of as
    bare assignments at module scope — avoids any accidental name clashes
    and makes the ownership of the planner parameter set explicit.
    """

    ATTACH_PLAN_PARAMETER: str = "container_attach_plan"
    ATTACH_COMPLETED_PARAMETER: str = "container_attach_completed"
    ATTACH_FINALIZED_PARAMETER: str = "container_attach_finalized"
    ATTACH_ERROR_PARAMETER: str = "container_attach_error_state"


class AttachmentPlanner:
    """Build, query, and validate the attachment plan for a CLI run.

    The planner is a context-bound service: it wraps a concrete
    ``CliContextPort`` together with the CLI parameter name that holds the
    plan dictionary (which allows the same class to be reused inside
    transaction helpers that temporarily stash a different plan on a
    different parameter key).

    Pure helpers that do not touch the CLI context (dataset path walking,
    dataset inspection, URI mapping, storage-conflict checks) are exposed
    as classmethods so they remain directly reusable by unit tests and by
    other storage services that do not go through the planner itself.
    """

    def __init__(
        self,
        context: CliContextPort,
        *,
        plan_parameter: Optional[str] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._plan_parameter: str = (
            plan_parameter
            or AttachmentPlanConstants.ATTACH_PLAN_PARAMETER
        )

    def get_plan(self) -> Optional[Dict[str, Any]]:
        value: Any = self._context.get_parameter_value(self._plan_parameter)
        if isinstance(value, dict):
            return value
        return None

    def require_plan(self) -> Dict[str, Any]:
        attachment_plan: Optional[Dict[str, Any]] = self.get_plan()
        if attachment_plan is None:
            self.inspect_container()
            attachment_plan = self.get_plan()
        if attachment_plan is None:
            raise InvalidContainerGraphError(
                "The container inspection did not produce an attachment plan."
            )
        return attachment_plan

    def require_resolved_plan(self) -> Dict[str, Any]:
        attachment_plan: Dict[str, Any] = self.require_plan()
        if not self.is_identity_resolved():
            self.resolve_identity()
            attachment_plan = self.require_plan()
        return attachment_plan

    def inspect_container(self) -> Dict[str, Any]:
        context: CliContextPort = self._context
        root_path: Path = Path(context.root_path).expanduser().resolve()
        raw_container_path: Any = context.get_parameter_value("container_path")
        normalized_path: str = str(raw_container_path or "").strip()
        if not normalized_path:
            raise InvalidContainerPathError(
                "Container path was not provided."
            )
        container_path: Path = Path(normalized_path).expanduser().resolve()
        if not container_path.is_dir():
            raise InvalidContainerPathError(
                f"Container path is not a directory: {container_path}"
            )
        try:
            container_path.relative_to(root_path)
        except ValueError as error:
            raise InvalidContainerPathError(
                "The container path must be inside the current project root: "
                f"{root_path}"
            ) from error

        container_file: Path = StorageBootstrap.get_container_storage_file_path(
            container_path
        )
        if not container_file.is_file():
            raise InvalidContainerPathError(
                f"Container metadata file was not found: {container_file}"
            )
        container_graph: Graph = AttachmentGraphOperations.load_graph(
            container_file,
            InvalidContainerGraphError,
        )
        container_subject: URIRef = AttachmentGraphOperations.single_subject(
            container_graph,
            RDF.type,
            _OBDC.DataContainer,
            InvalidContainerGraphError,
            "container",
        )
        source_container_id: str = AttachmentGraphOperations.required_literal(
            container_graph,
            container_subject,
            DCTERMS.identifier,
            InvalidContainerGraphError,
            "container identifier",
        )
        source_container_location: str = AttachmentGraphOperations.required_uri(
            container_graph,
            container_subject,
            PROV.atLocation,
            InvalidContainerGraphError,
            "container location",
        )
        for predicate, label in (
            (DCTERMS.title, "container title"),
            (_CT.description, "container description"),
            (_CT.creationDate, "container creation date"),
        ):
            AttachmentGraphOperations.required_literal(
                container_graph,
                container_subject,
                predicate,
                InvalidContainerGraphError,
                label,
            )

        storage_file: Path = StorageBootstrap.get_storage_file_path(root_path)
        if not storage_file.is_file():
            raise StorageIndexAttachError(
                f"Storage index was not found: {storage_file}"
            )
        AttachmentGraphOperations.load_graph(
            storage_file, StorageIndexAttachError
        )

        datasets: List[Dict[str, Any]] = [
            self._inspect_dataset(dataset_path, container_subject)
            for dataset_path in self._dataset_paths(container_path)
        ]
        attachment_plan: Dict[str, Any] = {
            "root_path": str(root_path),
            "container_path": str(container_path),
            "container_file": str(container_file),
            "storage_file": str(storage_file),
            "source_container_subject": str(container_subject),
            "source_container_id": source_container_id,
            "source_container_location": source_container_location,
            "context_snapshot": AttachmentTransactionCoordinator.snapshot_context(
                context
            ),
            "datasets": datasets,
        }
        context.set_parameter_value(self._plan_parameter, attachment_plan)
        context.delete_parameter(AttachmentPlanConstants.ATTACH_COMPLETED_PARAMETER)
        context.delete_parameter(AttachmentPlanConstants.ATTACH_FINALIZED_PARAMETER)
        context.delete_parameter(AttachmentPlanConstants.ATTACH_ERROR_PARAMETER)
        return {
            "container_path": str(container_path),
            "source_container_id": source_container_id,
            "dataset_count": len(datasets),
        }

    def is_container_inspected(self) -> bool:
        attachment_plan: Optional[Dict[str, Any]] = self.get_plan()
        if attachment_plan is None:
            return False
        return (
            Path(str(attachment_plan.get("container_file") or "")).is_file()
            and Path(str(attachment_plan.get("storage_file") or "")).is_file()
            and isinstance(attachment_plan.get("datasets"), list)
        )

    def resolve_identity(self) -> Dict[str, Any]:
        attachment_plan: Dict[str, Any] = self.require_plan()
        root_path: Path = Path(attachment_plan["root_path"]).resolve()
        container_path: Path = Path(attachment_plan["container_path"]).resolve()
        relative_container_path: Path = container_path.relative_to(root_path)
        encoded_container_path: str = quote(
            relative_container_path.as_posix(),
            safe="/",
        )
        target_container_id: str = (
            f"urn:ontobdc:storage/local/{encoded_container_path}"
        )
        target_container_location: str = container_path.as_uri()

        dataset_ids: Set[str] = set()
        for dataset in attachment_plan["datasets"]:
            dataset_path: Path = Path(dataset["path"]).resolve()
            relative_dataset_path: Path = dataset_path.relative_to(root_path)
            encoded_relative_dataset_path: str = quote(
                relative_dataset_path.as_posix(),
                safe="/",
            )
            target_dataset_id: str = (
                "urn:ontobdc:storage/dataset/"
                f"{encoded_relative_dataset_path}"
            )
            if target_dataset_id in dataset_ids:
                raise IdentityConflictError(
                    f"Two datasets resolve to the same identity: {target_dataset_id}"
                )
            dataset_ids.add(target_dataset_id)
            dataset["target_subject"] = target_dataset_id
            dataset["target_id"] = target_dataset_id
            dataset["target_location"] = dataset_path.as_uri()
            dataset["target_ontology_subject"] = Path(
                dataset["file"]
            ).resolve().as_uri()
            dataset["target_data_entity"] = (
                f"{target_dataset_id}/"
                f"{hashlib.sha256(target_dataset_id.encode('utf-8')).hexdigest()}"
            )

        attachment_plan["target_container_subject"] = target_container_id
        attachment_plan["target_container_id"] = target_container_id
        attachment_plan["target_container_location"] = target_container_location
        AttachmentPlanner.assert_no_storage_conflict(attachment_plan)
        self._context.set_parameter_value(self._plan_parameter, attachment_plan)
        return {
            "source_container_id": attachment_plan["source_container_id"],
            "target_container_id": target_container_id,
            "target_container_location": target_container_location,
            "dataset_count": len(attachment_plan["datasets"]),
        }

    def is_identity_resolved(self) -> bool:
        attachment_plan: Optional[Dict[str, Any]] = self.get_plan()
        if attachment_plan is None:
            return False
        required: tuple[Any, ...] = (
            attachment_plan.get("target_container_subject"),
            attachment_plan.get("target_container_id"),
            attachment_plan.get("target_container_location"),
        )
        if not all(isinstance(value, str) and value for value in required):
            return False
        datasets: Any = attachment_plan.get("datasets")
        if not isinstance(datasets, list):
            return False
        target_ids: List[str] = []
        for dataset in datasets:
            if not isinstance(dataset, dict):
                return False
            for key in (
                "target_subject",
                "target_id",
                "target_location",
                "target_ontology_subject",
                "target_data_entity",
            ):
                if not isinstance(dataset.get(key), str) or not dataset[key]:
                    return False
            target_ids.append(dataset["target_id"])
        return len(target_ids) == len(set(target_ids))

    @classmethod
    def uri_mapping(
        cls,
        attachment_plan: Dict[str, Any],
    ) -> Dict[URIRef, URIRef]:
        mapping: Dict[URIRef, URIRef] = {
            URIRef(attachment_plan["source_container_subject"]): URIRef(
                attachment_plan["target_container_subject"]
            )
        }
        for dataset in attachment_plan["datasets"]:
            mapping[URIRef(dataset["source_subject"])] = URIRef(
                dataset["target_subject"]
            )
            mapping[URIRef(dataset["source_container_subject"])] = URIRef(
                attachment_plan["target_container_subject"]
            )
            for source in dataset["source_ontology_subjects"]:
                mapping[URIRef(source)] = URIRef(
                    dataset["target_ontology_subject"]
                )
            for source in dataset["source_data_entities"]:
                mapping[URIRef(source)] = URIRef(
                    dataset["target_data_entity"]
                )
        return mapping

    @classmethod
    def assert_no_storage_conflict(
        cls,
        attachment_plan: Dict[str, Any],
    ) -> None:
        storage_graph: Graph = AttachmentGraphOperations.load_graph(
            Path(attachment_plan["storage_file"]),
            StorageIndexAttachError,
        )
        source_subject: URIRef = URIRef(
            attachment_plan["source_container_subject"]
        )
        target_subject: URIRef = URIRef(
            attachment_plan["target_container_subject"]
        )
        source_id: str = attachment_plan["source_container_id"]
        target_id: str = attachment_plan["target_container_id"]
        source_location: str = attachment_plan["source_container_location"]
        target_location: str = attachment_plan["target_container_location"]
        for subject in storage_graph.subjects(RDF.type, _OBDC.DataContainer):
            if not isinstance(subject, URIRef):
                continue
            identifiers: Set[str] = {
                str(value).strip()
                for value in storage_graph.objects(subject, DCTERMS.identifier)
            }
            locations: Set[str] = {
                str(value).strip()
                for value in storage_graph.objects(subject, PROV.atLocation)
            }
            represents_imported_container: bool = (
                subject == source_subject
                or source_id in identifiers
                or source_location in locations
            )
            targets_local_identity: bool = (
                subject == target_subject
                or target_id in identifiers
                or target_location in locations
            )
            if targets_local_identity and not represents_imported_container:
                raise IdentityConflictError(
                    "The target container identity or location is already used by "
                    f"another storage entry: {subject}"
                )

    @classmethod
    def _dataset_paths(cls, container_path: Path) -> List[Path]:
        return sorted(
            candidate.resolve()
            for candidate in container_path.iterdir()
            if candidate.is_dir()
            and StorageBootstrap.get_dataset_storage_file_path(
                candidate
            ).is_file()
        )

    @classmethod
    def _inspect_dataset(
        cls,
        dataset_path: Path,
        container_subject: URIRef,
    ) -> Dict[str, Any]:
        dataset_file: Path = StorageBootstrap.get_dataset_storage_file_path(
            dataset_path
        )
        dataset_graph: Graph = AttachmentGraphOperations.load_graph(
            dataset_file, DatasetAttachError
        )
        dataset_subject: URIRef = AttachmentGraphOperations.single_subject(
            dataset_graph,
            RDF.type,
            _OBDC.EntityDataset,
            DatasetAttachError,
            "dataset",
        )
        source_dataset_id: str = AttachmentGraphOperations.required_literal(
            dataset_graph,
            dataset_subject,
            DCTERMS.identifier,
            DatasetAttachError,
            "dataset identifier",
        )
        source_dataset_location: str = AttachmentGraphOperations.required_uri(
            dataset_graph,
            dataset_subject,
            PROV.atLocation,
            DatasetAttachError,
            "dataset location",
        )
        source_container_subject: str = AttachmentGraphOperations.required_uri(
            dataset_graph,
            dataset_subject,
            _OBDC.belongsToDataContainer,
            DatasetAttachError,
            "dataset container reference",
        )
        if source_container_subject != str(container_subject):
            raise DatasetAttachError(
                "Dataset container reference does not match the imported "
                f"container: {dataset_path}"
            )
        for predicate, label in (
            (DCTERMS.title, "dataset title"),
            (DCTERMS.description, "dataset description"),
            (_CT.creationDate, "dataset creation date"),
        ):
            AttachmentGraphOperations.required_literal(
                dataset_graph,
                dataset_subject,
                predicate,
                DatasetAttachError,
                label,
            )
        ontology_subjects: List[str] = [
            str(subject)
            for subject in dataset_graph.subjects(RDF.type, OWL.Ontology)
            if isinstance(subject, URIRef)
        ]
        if len(ontology_subjects) != 1:
            raise DatasetAttachError(
                f"Expected exactly one dataset ontology subject: {dataset_file}"
            )
        data_entities: List[str] = [
            str(value)
            for value in dataset_graph.objects(
                dataset_subject,
                _OBDC.hasDataEntity,
            )
            if isinstance(value, URIRef)
        ]
        if len(data_entities) != 1:
            raise DatasetAttachError(
                f"Expected exactly one dataset data entity: {dataset_file}"
            )
        return {
            "path": str(dataset_path),
            "file": str(dataset_file),
            "source_subject": str(dataset_subject),
            "source_id": source_dataset_id,
            "source_location": source_dataset_location,
            "source_container_subject": source_container_subject,
            "source_ontology_subjects": ontology_subjects,
            "source_data_entities": data_entities,
        }
