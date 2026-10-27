from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.init_config import InitContainerFiles
from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_config_adapter_ready.check import main as check_config_adapter_ready
from ontobdc.cli.plugin.check.is_config_adapter_ready.hotfix import main as hotfix_config_adapter_ready
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ConfigAdapterReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.config_adapter_ready",
        version="1.0.0",
        name="Config Adapter Ready",
        description="Ensure that config.yaml declares the container root.",
        author=["TRAE"],
        tags=['cli', 'init', 'config'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "Config.yaml was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing config.yaml to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.CONFIG_ADAPTER_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.CONFIG_ADAPTER_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_config_adapter_ready,
            hotfix_config_adapter_ready,
            root_path,
            "config.yaml",
        )
        return {
            "resulting_state": CliInitProcessState.CONFIG_ADAPTER_READY,
            "config_file": str(InitContainerFiles.config_file(str(root_path))),
        }
