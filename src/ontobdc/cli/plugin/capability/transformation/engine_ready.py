from pathlib import Path
from typing import Any, Dict

from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_engine_ready.check import main as check_engine_ready
from ontobdc.cli.plugin.check.is_engine_ready.hotfix import main as hotfix_engine_ready
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class EngineReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.engine_ready",
        version="1.0.0",
        name="Engine Ready",
        description="Ensure that the project config declares the engine.",
        author=["TRAE"],
        tags=['cli', 'init', 'engine'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The engine entry of config.yaml was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing the engine entry of config.yaml to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.ENGINE_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.ENGINE_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_engine_ready,
            hotfix_engine_ready,
            root_path,
            "the engine entry of config.yaml",
        )
        return {
            "resulting_state": CliInitProcessState.ENGINE_READY,
            "engine": str(ConfigDataAdapter(root_dir=str(root_path)).all.get("engine")),
        }
