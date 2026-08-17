from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.plugin.check.is_root_set.check import main as check_storage_index
from ontobdc.storage.plugin.check.is_root_set.hotfix import main as hotfix_storage_index

class StorageIndexHealthyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.storage_index_healthy",
        version="1.0.0",
        name="Storage Index Healthy",
        description="Ensure that storage.ttl exists and conforms to the CLI init checks.",
        author=["TRAE"],
        tags=["cli", "init", "storage"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Storage index was validated against the CLI initialization "
                    "contract; no issues were detected."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the storage index against the CLI "
                    "initialization contract."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Storage Index Healthy"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the storage.ttl bootstrap index."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = StorageBootstrap.get_init_root_path(context=context)
        if check_storage_index(root_path=str(root_path)) != 0:
            if hotfix_storage_index(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix storage.ttl during CLI init.")

        if check_storage_index(root_path=str(root_path)) != 0:
            raise ValueError("storage.ttl is still invalid after the CLI init hotfix.")

        return {
            "resulting_state": CliInitProcessState.STORAGE_INDEX_HEALTHY,
            "storage_file": str(StorageBootstrap.get_storage_file_path(root_path)),
        }
