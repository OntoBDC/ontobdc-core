from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_ontobdc_directory_ready.check import main as check_ontobdc_directory_ready
from ontobdc.cli.plugin.check.is_ontobdc_directory_ready.hotfix import main as hotfix_ontobdc_directory_ready
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class OntobdcDirectoryReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.ontobdc_directory_ready",
        version="1.0.0",
        name="OntoBDC Directory Ready",
        description="Ensure that the target directory contains the .__ontobdc__ directory.",
        author=["TRAE"],
        tags=['cli', 'init', 'directory'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The .__ontobdc__ directory was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing the .__ontobdc__ directory to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.ONTOBDC_DIRECTORY_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.ONTOBDC_DIRECTORY_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_ontobdc_directory_ready,
            hotfix_ontobdc_directory_ready,
            root_path,
            "the .__ontobdc__ directory",
        )
        return {
            "resulting_state": CliInitProcessState.ONTOBDC_DIRECTORY_READY,
            "ontobdc_directory": str(StorageBootstrap.get_ontobdc_directory(root_path)),
        }
