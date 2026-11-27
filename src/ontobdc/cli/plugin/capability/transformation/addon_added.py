from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.plugin.machine.init_addon.request import CliInitAddonRequest
from ontobdc.cli.plugin.machine.init_addon.state import CliInitAddonProcessState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.storage_addons import StorageAddons


class AddonAddedCapability(TransactionCapability):
    """
    Adds the addon that was located: it looks in the ``storage.ttl`` for the addon installed, and when there is none it
    copies the folder to the ``addon`` folder of the storage and models the addon in the ``storage.ttl``.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.cli.plugin.capability.transformation.target.addon_added",
        version="1.0.0",
        name="Addon Added",
        description="Install the addon that was located in the storage, and model it in the storage.ttl.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["cli", "init", "addon"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The addon was added."},
            "debug_entry": {"en": "Adding the addon."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return CliInitAddonProcessState.ADDON_ADDED.label(lang)

    def description(self, lang: str = "en") -> str:
        return CliInitAddonProcessState.ADDON_ADDED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        folder: Path = Path(RequiredParameter.of(context, CliInitAddonRequest.FOLDER_KEY))
        source: str = CliInitAddonRequest.source(context)
        installed: Dict[str, Any] = StorageAddons.install(Path(StorageFileLocator.resolve()), folder, source)

        return {"resulting_state": CliInitAddonProcessState.ADDON_ADDED, **installed}
