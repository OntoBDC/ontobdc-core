from typing import Any, Dict

from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.check.has_valid_brand.check import main as check_brand
from ontobdc.cli.plugin.check.has_valid_brand.hotfix import main as hotfix_brand
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class BrandReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.brand_ready",
        version="1.0.0",
        name="Brand Ready",
        description="Ensure that the project brand (name, mark_svg, logotype_svg, slogan) is configured and valid for the CLI init flow.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "init", "brand", "view"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Project brand configuration was validated and is ready for CLI "
                    "initialization."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the project brand configuration for CLI "
                    "initialization."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitProcessState.BRAND_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitProcessState.BRAND_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        root_path = StorageBootstrap.get_init_root_path(context=context)
        if check_brand(root_path=str(root_path)) != 0:
            if hotfix_brand(root_path=str(root_path)) != 0:
                raise ValueError("Failed to hotfix brand during CLI init.")

        if check_brand(root_path=str(root_path)) != 0:
            raise ValueError("brand is still invalid after the CLI init hotfix.")

        config_adapter: ConfigDataAdapter = ConfigDataAdapter(root_dir=str(root_path))
        brand: Dict[str, Any] = dict(config_adapter.all.get("brand") or {})
        return {
            "resulting_state": CliInitProcessState.BRAND_READY,
            "brand_name": brand.get("name"),
        }
