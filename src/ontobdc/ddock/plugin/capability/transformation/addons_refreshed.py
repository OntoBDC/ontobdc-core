import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.folder_merge import FolderMerge
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.adapter.zip_archive import ZipArchive
from ontobdc.ddock.adapter.local_package import LocalPackage
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_update.machine import SystemUpdateRequest
from ontobdc.ddock.plugin.machine.system_update.state import SystemUpdateProcessState


class AddonsRefreshedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.addons_refreshed",
        version="1.0.0",
        name="Addons Refreshed",
        description="Download again the folder each package of system.obdc names and put the one that holds an addon into the addon folder of the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "update", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Addons Refreshed."},
            "debug_entry": {"en": "Reaching the state Addons Refreshed."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Addons Atualizados"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # Putting the addons of the packages back is not a fact kept on disk
        # that says it was this run that did it, so each update does it once.
        return SystemUpdateRequest.addons_refreshed(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemUpdateRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        destination: Path = container_path / descriptor.source.local / SystemDescriptors.ADDON_FOLDER_NAME
        refreshed: List[str] = []
        without_addon: List[str] = []
        index: int
        address: str
        for index, address in enumerate(descriptor.packages):
            addon: Optional[Path] = self._addon_of(context, container_path, index, address)
            if addon is None:
                without_addon.append(address)
                continue

            target: Path = destination / addon.name
            shutil.rmtree(target, ignore_errors=True)
            FolderMerge.merge(addon, target)
            refreshed.append(addon.name)

        context.set_parameter_value(SystemUpdateRequest.ADDONS_REFRESHED_KEY, True)

        return {
            "resulting_state": SystemUpdateProcessState.ADDONS_REFRESHED,
            "addons": refreshed,
            "packages_without_addon": without_addon,
        }

    @classmethod
    def _addon_of(cls, context: CliContextPort, container_path: Path, index: int, address: str) -> Optional[Path]:
        """
        The folder of the addon the package at ``index`` names, downloaded
        into the work folder, or nothing when the address names no folder of
        the repository or the folder it names is not an addon. A relative path
        is the folder of the addon itself, and it is copied to the work folder,
        because what is merged is moved from there.
        """
        if LocalPackage.is_path(address):
            # The addon is known by the name of its folder, so the copy goes into a folder of that name.
            holder: Path = SystemUpdateRequest.addon_path(context, index)
            copied: Path = holder / LocalPackage.folder(container_path, address).name
            SystemUpdateRequest.discard_fetch(holder)
            LocalPackage.copy(container_path, address, copied)
            if SystemDescriptors.is_local_addon(copied):
                return copied
            if not (copied / "src" / "host").is_dir():
                raise ValueError(
                    f"The package {address} is neither an addon (a system.obdc of scope 'addon', or a package.json) "
                    "nor holds a src/host."
                )
            return None

        folder: Optional[str] = GitHubZipAddress.folder(address)
        if folder is None:
            return None

        zip_address: Optional[str] = GitHubZipAddress.resolve(address)
        if zip_address is None:
            raise ValueError(f"The package {address} has no zip of its master or its main branch.")

        target: Path = SystemUpdateRequest.addon_path(context, index)
        SystemUpdateRequest.discard_fetch(target)
        ZipArchive.fetch(zip_address, target)

        addon: Path = target / folder
        return addon if SystemDescriptors.is_addon(addon) else None
