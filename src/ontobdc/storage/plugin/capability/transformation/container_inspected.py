from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment.plan import AttachmentPlanner
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class ContainerInspectedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_inspected"
        ),
        version="1.0.0",
        name="Container Inspected",
        description=(
            "Inspect the imported container and its datasets without changing metadata."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Imported container and dataset structure was inspected without "
                    "modifying metadata."
                ),
            },
            "debug_entry": {
                "en": (
                    "Inspecting the imported container and dataset "
                    "structure without modifying metadata."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_INSPECTED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_INSPECTED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = AttachmentPlanner(context).inspect_container()
        result["resulting_state"] = (
            ContainerAttachProcessState.CONTAINER_INSPECTED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return AttachmentPlanner(context).is_container_inspected()
