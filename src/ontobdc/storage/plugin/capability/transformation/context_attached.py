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


class ContextAttachedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "context_attached"
        ),
        version="1.0.0",
        name="Context Attached",
        description=(
            "Bind the execution context to the attached container and clear stale update selectors."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Execution context was bound to the attached container and stale "
                    "update selectors were cleared."
                ),
            },
            "debug_entry": {
                "en": (
                    "Binding the execution context to the attached "
                    "container and clearing stale update selectors."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTEXT_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTEXT_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = AttachmentContextManager(context).attach_context()
        result["resulting_state"] = (
            ContainerAttachProcessState.CONTEXT_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return AttachmentContextManager(context).is_context_attached()
