from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_storage_index_healthy.check import main as check_storage_index_healthy
from ontobdc.cli.plugin.check.is_storage_index_healthy.hotfix import main as hotfix_storage_index_healthy
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class StorageIndexHealthyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.storage_index_healthy",
        version="1.0.0",
        name="Storage Index Healthy",
        description="Ensure that storage.ttl describes the main storage.",
        author=["TRAE"],
        tags=['cli', 'init', 'storage'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "Storage.ttl was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing storage.ttl to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.STORAGE_INDEX_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.STORAGE_INDEX_HEALTHY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_storage_index_healthy,
            hotfix_storage_index_healthy,
            root_path,
            "storage.ttl",
        )
        return {
            "resulting_state": CliInitProcessState.STORAGE_INDEX_HEALTHY,
            "storage_file": str(StorageBootstrap.get_storage_file_path(root_path)),
        }
