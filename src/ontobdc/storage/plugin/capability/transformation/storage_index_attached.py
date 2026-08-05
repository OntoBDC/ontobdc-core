from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.attachment import (
    attach_storage_index,
    is_storage_index_attached,
)
from ontobdc.storage.domain.machine.attach_state import (
    ContainerAttachProcessState,
)


class StorageIndexAttachedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "storage_index_attached"
        ),
        version="1.0.0",
        name="Storage Index Attached",
        description=(
            "Reconcile the local storage index with the attached container metadata."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "attach", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.STORAGE_INDEX_ATTACHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerAttachProcessState.STORAGE_INDEX_ATTACHED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result = attach_storage_index(context)
        result["resulting_state"] = (
            ContainerAttachProcessState.STORAGE_INDEX_ATTACHED
        )
        return result

    def is_satisfied(self, context: CliContextPort) -> bool:
        return is_storage_index_attached(context)
