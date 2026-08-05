from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment import (
    complete_attachment,
    is_container_attached,
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
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = complete_attachment(context)
        result["resulting_state"] = (
            ContainerAttachProcessState.CONTAINER_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return is_container_attached(context)
