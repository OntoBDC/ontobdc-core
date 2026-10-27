from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.adapter.zip_archive import ZipArchive

from ontobdc.ddock.adapter.system_lock import SystemLock

from ontobdc.ddock.adapter.folder_merge import FolderMerge

from ontobdc.ddock.domain.model.system_install import ArchiveFiles

class PackagesExtractedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.packages_extracted",
        version="1.0.0",
        name="Packages Extracted",
        description="Download the zip of each package of system.obdc and unpack it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Packages Extracted."},
            "debug_entry": {"en": "Reaching the state Packages Extracted."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Pacotes Descompactados"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # Only the packages the lock does not have yet are downloaded.
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        pending: List[str] = SystemLock.pending_packages(container_path, descriptor)
        extracted: List[str] = [package.address for package in SystemInstallRequest.packages(context, descriptor.packages)]
        return all(address in extracted for address in pending)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        pending: List[str] = SystemLock.pending_packages(container_path, descriptor)
        extracted: List[str] = [package.address for package in SystemInstallRequest.packages(context, descriptor.packages)]
        fetched: List[str] = []
        index: int
        address: str
        for index, address in enumerate(descriptor.packages):
            if address not in pending or address in extracted:
                continue

            zip_address = GitHubZipAddress.resolve(address)
            if zip_address is None:
                raise ValueError(f"The package {address} has no zip of its master or its main branch.")

            target: Path = SystemInstallRequest.package_path(context, index)
            SystemInstallRequest.discard_fetch(target)
            sha256: str = ZipArchive.fetch(zip_address, target)
            SystemInstallRequest.record_fetch(
                target,
                ArchiveFiles(zip=zip_address, sha256=sha256, files=FolderMerge.files(target / "src" / "host")),
            )
            fetched.append(address)

        return {
            "resulting_state": SystemInstallProcessState.PACKAGES_EXTRACTED,
            "packages": fetched,
        }
