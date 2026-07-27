from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.has_valid_config_file.check import main as check_config_file
from ontobdc.cli.plugin.check.has_valid_config_file.hotfix import main as hotfix_config_file
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import get_init_root_path


class ConfigAdapterReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.config_adapter_ready",
        version="1.0.0",
        name="Config Adapter Ready",
        description="Ensure that config.yaml exists and conforms to the init bootstrap contract.",
        author=["TRAE"],
        tags=["cli", "init", "config"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Config Adapter Ready"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the bootstrap config.yaml file."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = get_init_root_path(context=context)
        if check_config_file(root_path=str(root_path)) != 0:
            if hotfix_config_file(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix config.yaml during CLI init.")

        if check_config_file(root_path=str(root_path)) != 0:
            raise ValueError("config.yaml is still invalid after the CLI init hotfix.")

        return {
            "resulting_state": CliInitProcessState.CONFIG_ADAPTER_READY,
            "config_file": str(root_path / ".__ontobdc__" / "config.yaml"),
        }
