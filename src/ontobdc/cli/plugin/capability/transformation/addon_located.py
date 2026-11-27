from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.machine.init_addon.request import CliInitAddonRequest
from ontobdc.cli.plugin.machine.init_addon.state import CliInitAddonProcessState
from ontobdc.shared.adapter.addon_locator import AddonLocator
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class AddonLocatedCapability(TransactionCapability):
    """
    Locates the folder of the addon: the folder the source names, or the folder of a repository of GitHub that its address
    names, brought to this machine. The folder has to have the ``ontobdc`` folder with the code of the addon.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.addon_located",
        version="1.0.0",
        name="Addon Located",
        description="Locate the folder of the addon from the folder or the address it was given as.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "init", "addon"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The folder of the addon was located."},
            "debug_entry": {"en": "Locating the folder of the addon."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitAddonProcessState.ADDON_LOCATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitAddonProcessState.ADDON_LOCATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        source: str = CliInitAddonRequest.source(context)
        addon: Path = AddonLocator.locate(source)
        context.set_parameter_value(CliInitAddonRequest.FOLDER_KEY, str(addon))

        return {
            "resulting_state": CliInitAddonProcessState.ADDON_LOCATED,
            "source": source,
            "addon": str(addon),
        }
