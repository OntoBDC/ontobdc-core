from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.has_valid_engine.check import main as check_engine
from ontobdc.cli.plugin.check.has_valid_engine.hotfix import main as hotfix_engine
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class EngineReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.engine_ready",
        version="1.0.0",
        name="Engine Ready",
        description="Ensure that the project engine is configured and valid for the CLI init flow.",
        author=["TRAE"],
        tags=["cli", "init", "engine"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Project engine configuration was validated and is ready for CLI "
                    "initialization."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the project engine configuration for CLI "
                    "initialization."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Engine Ready"

    def description(self, lang: str = "en") -> str:
        return "Repairs and validates the engine entry in the bootstrap config."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = StorageBootstrap.get_init_root_path(context=context)
        if check_engine(root_path=str(root_path)) != 0:
            if hotfix_engine(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix engine during CLI init.")

        if check_engine(root_path=str(root_path)) != 0:
            raise ValueError("engine is still invalid after the CLI init hotfix.")

        config_adapter: ConfigDataAdapter = ConfigDataAdapter(root_dir=str(root_path))
        engine: str = str(config_adapter.all.get("engine"))
        return {
            "resulting_state": CliInitProcessState.ENGINE_READY,
            "engine": engine,
        }
