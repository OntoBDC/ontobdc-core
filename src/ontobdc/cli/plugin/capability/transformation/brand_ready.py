from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.adapter.init_config import InitProjectFiles
from ontobdc.cli.adapter.repair import CheckedRepair
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.is_brand_ready.check import main as check_brand_ready
from ontobdc.cli.plugin.check.is_brand_ready.hotfix import main as hotfix_brand_ready
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class BrandReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.brand_ready",
        version="1.0.0",
        name="Brand Ready",
        description="Ensure that the project config declares the brand.",
        author=["TRAE"],
        tags=['cli', 'init', 'brand'],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The brand entry of config.yaml was brought to what the init checks observe.",
            },
            "debug_entry": {
                "en": "Bringing the brand entry of config.yaml to what the init checks observe.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.BRAND_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.BRAND_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        CheckedRepair.ensure(
            check_brand_ready,
            hotfix_brand_ready,
            root_path,
            "the brand entry of config.yaml",
        )
        return {
            "resulting_state": CliInitProcessState.BRAND_READY,
            "brand": dict(InitProjectFiles.read_config(str(root_path)).get("brand", {})),
        }
