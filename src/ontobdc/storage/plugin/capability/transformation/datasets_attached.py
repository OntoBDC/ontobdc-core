from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment.metadata import (
    AttachmentMetadataService,
)
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class DatasetsAttachedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "datasets_attached"
        ),
        version="1.0.0",
        name="Datasets Attached",
        description=(
            "Rewrite dataset identities and synchronize their summaries in the container graph."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Dataset identities were rewritten and their summaries were "
                    "synchronized in the container graph."
                ),
            },
            "debug_entry": {
                "en": (
                    "Rewriting dataset identities and synchronizing their "
                    "summaries in the container graph."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.DATASETS_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.DATASETS_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = AttachmentMetadataService.attach_datasets(context)
        result["resulting_state"] = (
            ContainerAttachProcessState.DATASETS_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return AttachmentMetadataService.is_datasets_attached(context)
