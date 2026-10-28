from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.folder_merge import FolderMerge
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.adapter.zip_archive import ZipArchive
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.domain.model.system_install import ArchiveFiles
from ontobdc.ddock.plugin.machine.system_update.machine import SystemUpdateRequest
from ontobdc.ddock.plugin.machine.system_update.state import SystemUpdateProcessState


class PackagesRefreshedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.packages_refreshed",
        version="1.0.0",
        name="Packages Refreshed",
        description="Download the zip of each package of system.obdc again and put its host into the source folder of the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "update", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Packages Refreshed."},
            "debug_entry": {"en": "Reaching the state Packages Refreshed."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Pacotes Atualizados"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # Putting the host of the packages back is not a fact kept on disk that
        # says it was this run that did it, so each update does it once.
        return SystemUpdateRequest.packages_refreshed(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemUpdateRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        destination: Path = container_path / descriptor.source.local
        fetched: List[str] = []
        index: int
        address: str
        for index, address in enumerate(descriptor.packages):
            zip_address: Optional[str] = GitHubZipAddress.resolve(address)
            if zip_address is None:
                raise ValueError(f"The package {address} has no zip of its master or its main branch.")

            target: Path = SystemUpdateRequest.package_path(context, index)
            SystemUpdateRequest.discard_fetch(target)
            sha256: str = ZipArchive.fetch(zip_address, target)
            host: Path = target / "src" / "host"
            SystemUpdateRequest.record_fetch(
                target,
                ArchiveFiles(zip=zip_address, sha256=sha256, files=FolderMerge.files(host)),
            )
            if host.is_dir():
                FolderMerge.merge(host, destination)
            fetched.append(address)

        context.set_parameter_value(SystemUpdateRequest.PACKAGES_REFRESHED_KEY, True)

        return {
            "resulting_state": SystemUpdateProcessState.PACKAGES_REFRESHED,
            "packages": fetched,
        }
