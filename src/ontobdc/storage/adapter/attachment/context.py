from pathlib import Path
from typing import Any, Dict, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.attachment.error import (
    ContainerAttachError,
)
from ontobdc.storage.adapter.attachment.graph import (
    AttachmentGraphNamespaceBootstrap,
    AttachmentGraphOperations,
)
from ontobdc.storage.adapter.attachment.metadata import (
    AttachmentMetadataService,
)
from ontobdc.storage.adapter.attachment.plan import (
    AttachmentPlanner,
    AttachmentPlanConstants,
)
from ontobdc.storage.adapter.attachment.transaction import (
    AttachmentTransactionCoordinator,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


AttachmentGraphNamespaceBootstrap.initialize()
_CT = AttachmentGraphNamespaceBootstrap.CT
_OBDC = AttachmentGraphNamespaceBootstrap.OBDC


class AttachmentContextManager:
    """Manage the CLI context lifecycle around a container attachment."""

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

    def attach_context(self) -> Dict[str, Any]:
        context: CliContextPort = self._context
        if AttachmentMetadataService(context).is_container_metadata_attached():
            metadata_summary: Dict[str, Any] = {
                "container_metadata_attached": True,
            }
        else:
            metadata_summary = AttachmentMetadataService(
                context
            ).attach_container_metadata()

        attachment_plan: Dict[str, Any] = AttachmentPlanner(
            context
        ).require_plan()
        container_file: Path = Path(attachment_plan["container_file"])
        container_graph: Graph = AttachmentGraphOperations.load_graph(
            container_file,
            ContainerAttachError,
        )
        target_container_subject: URIRef = (
            AttachmentGraphOperations.single_subject(
                container_graph,
                RDF.type,
                _OBDC.DataContainer,
                ContainerAttachError,
                "container",
            )
        )
        container_id: str = AttachmentGraphOperations.required_literal(
            container_graph,
            target_container_subject,
            DCTERMS.identifier,
            ContainerAttachError,
            "container identifier",
        )
        container_title: str = AttachmentGraphOperations.required_literal(
            container_graph,
            target_container_subject,
            DCTERMS.title,
            ContainerAttachError,
            "container title",
        )
        container_description: str = AttachmentGraphOperations.required_literal(
            container_graph,
            target_container_subject,
            _CT.description,
            ContainerAttachError,
            "container description",
        )
        container_creation_date: str = AttachmentGraphOperations.required_literal(
            container_graph,
            target_container_subject,
            _CT.creationDate,
            ContainerAttachError,
            "container creation date",
        )
        container_location: str = AttachmentGraphOperations.required_uri(
            container_graph,
            target_container_subject,
            PROV.atLocation,
            ContainerAttachError,
            "container location",
        )

        context_graph: Graph = Graph()
        for prefix, namespace in container_graph.namespaces():
            context_graph.bind(prefix, namespace)
        context_graph.add(
            (target_container_subject, RDF.type, _OBDC.DataContainer)
        )
        context_graph.add(
            (
                target_container_subject,
                DCTERMS.title,
                Literal(container_title),
            )
        )
        context_graph.add(
            (
                target_container_subject,
                _CT.description,
                Literal(container_description),
            )
        )
        context_graph.add(
            (
                target_container_subject,
                _CT.creationDate,
                Literal(container_creation_date),
            )
        )
        AttachmentGraphOperations.set_single(
            context_graph,
            target_container_subject,
            DCTERMS.identifier,
            Literal(container_id),
        )
        AttachmentGraphOperations.set_single(
            context_graph,
            target_container_subject,
            PROV.atLocation,
            container_location,
        )
        context_file: Path = StorageBootstrap.get_context_file_path(
            Path(StorageBootstrap.get_init_root_path())
        )
        context_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            context_graph.serialize(
                str(context_file),
                format="turtle",
                encoding="utf-8",
            )
        except Exception as error:
            raise ContainerAttachError(
                f"Could not write attachment context graph: {context_file}"
            ) from error

        crate_metadata_file: Path = (
            StorageBootstrap.get_container_crate_metadata_file_path(
                Path(attachment_plan["container_path"])
            )
        )
        try:
            container_graph.serialize(
                str(crate_metadata_file),
                format="turtle",
                encoding="utf-8",
            )
        except Exception as error:
            raise ContainerAttachError(
                "Could not write RO-Crate container metadata: "
                f"{crate_metadata_file}"
            ) from error

        return {
            **metadata_summary,
            "context_file": str(context_file),
            "crate_metadata_file": str(crate_metadata_file),
        }

    def is_context_attached(self) -> bool:
        attachment_plan: Optional[Dict[str, Any]] = AttachmentPlanner(
            self._context
        ).get_plan()
        if attachment_plan is None:
            return False
        context_file: Path = StorageBootstrap.get_context_file_path(
            Path(attachment_plan["container_path"])
        )
        return context_file.is_file()

    def complete_attachment(self) -> Dict[str, Any]:
        context: CliContextPort = self._context
        attachment_plan: Optional[Dict[str, Any]] = AttachmentPlanner(
            context
        ).require_plan()
        if not AttachmentMetadataService(
            context
        ).is_container_metadata_attached():
            raise ContainerAttachError(
                "Container metadata was not attached; refusing to mark the "
                "operation complete."
            )
        context_file_exists: bool = self.is_context_attached()
        AttachmentTransactionCoordinator(
            context=None,  # type: ignore[arg-type]
            plan=attachment_plan,
            plan_parameter=self._plan_parameter,
        ).discard_backup()
        context.set_parameter_value(
            AttachmentPlanConstants.ATTACH_FINALIZED_PARAMETER,
            str(Path(attachment_plan["container_path"]).resolve()),
        )
        context.delete_parameter(self._plan_parameter)
        context.delete_parameter(self._completed_parameter)
        context.delete_parameter(self._error_parameter)
        return {
            "context_file_exists": context_file_exists,
            "container_id": attachment_plan["target_container_id"],
            "container_path": attachment_plan["container_path"],
        }

    def is_container_attached(self) -> bool:
        finalized: Any = self._context.get_parameter_value(
            AttachmentPlanConstants.ATTACH_FINALIZED_PARAMETER
        )
        container_path: Any = self._context.get_parameter_value(
            "container_path"
        )
        if not isinstance(finalized, str) or not isinstance(
            container_path,
            str,
        ):
            return False
        return Path(finalized).resolve() == Path(container_path).resolve()

    def rollback_attachment(self) -> Dict[str, Any]:
        context: CliContextPort = self._context
        attachment_plan: Any = context.get_parameter_value(
            self._plan_parameter
        )
        if not isinstance(attachment_plan, dict):
            raise ContainerAttachError(
                "There is no attachment plan in the context."
            )
        try:
            AttachmentTransactionCoordinator(
                context,
                attachment_plan,
                self._plan_parameter,
            ).restore()
        except Exception as error:
            raise ContainerAttachError(
                f"Could not restore attachment backup: {error}"
            ) from error
        context.delete_parameter(self._plan_parameter)
        context.delete_parameter(self._completed_parameter)
        context.delete_parameter(
            AttachmentPlanConstants.ATTACH_FINALIZED_PARAMETER
        )
        context.delete_parameter(self._error_parameter)
        return {
            "rolled_back_container_id": attachment_plan.get(
                "target_container_id"
            ),
            "container_path": attachment_plan.get("container_path"),
        }
