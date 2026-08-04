from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import (
    CapabilityExecutor,
    TransactionCapability,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState


class ContainerHtmlViewUpdatedCapability(TransactionCapability):
    """Regenerate an existing root index.html through a supplied view capability."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_html_view_updated"
        ),
        version="1.0.0",
        name="Updated Container HTML View",
        description=(
            "Regenerate an existing container index.html through the view update "
            "capability supplied by the active application."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "view", "html"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_html_view_update_capability": {
                    "type": CapabilityPort,
                    "required": True,
                    "description": (
                        "Application capability responsible for regenerating the "
                        "existing container index.html."
                    ),
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        index_path: Path = container_path / "index.html"
        if not index_path.is_file():
            raise ValueError(
                "Container HTML view update was requested, but index.html does "
                f"not exist: {index_path}"
            )

        update_capability: Any = context.get_parameter_value(
            "container_html_view_update_capability"
        )
        if not isinstance(update_capability, CapabilityPort):
            raise ValueError(
                "A container_html_view_update_capability is required to "
                "regenerate an existing index.html."
            )

        delegated_metadata: Any = getattr(update_capability, "metadata", None)
        delegated_id: str = str(
            getattr(delegated_metadata, "id", "") or ""
        ).strip()
        if delegated_id == self.metadata.id:
            raise ValueError(
                "The container HTML view update capability cannot delegate to "
                "itself."
            )

        delegated_result: Dict[str, Any] = CapabilityExecutor.execute(
            update_capability,
            context,
        )
        if not index_path.is_file():
            raise ValueError(
                "The delegated view update capability removed the container "
                f"index.html: {index_path}"
            )

        context.set_parameter_value("container_html_view_updated", True)

        return {
            "resulting_state": (
                ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED
            ),
            "container_path": str(container_path),
            "index_path": str(index_path),
            "reused_capability": delegated_result,
        }
