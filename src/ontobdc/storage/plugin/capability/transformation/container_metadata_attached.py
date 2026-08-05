from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment import (
    attach_container_metadata,
    is_container_metadata_attached,
)
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class ContainerMetadataAttachedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_metadata_attached"
        ),
        version="1.0.0",
        name="Container Metadata Attached",
        description=(
            "Rewrite the container metadata graph with the target local identity and location."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = attach_container_metadata(context)
        result["resulting_state"] = (
            ContainerAttachProcessState.CONTAINER_METADATA_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return is_container_metadata_attached(context)
