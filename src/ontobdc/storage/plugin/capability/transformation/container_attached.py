from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment.context import (
    AttachmentContextManager,
)
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class ContainerAttachedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_attached"
        ),
        version="1.0.0",
        name="Container Attached",
        description=(
            "Validate the complete attachment and mark the operation as complete."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container attachment was validated and marked complete."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the container attachment and marking it "
                    "complete."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = AttachmentContextManager(context).complete_attachment()
        result["resulting_state"] = (
            ContainerAttachProcessState.CONTAINER_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return AttachmentContextManager(context).is_container_attached()
