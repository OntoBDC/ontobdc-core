from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.folder_merge import FolderMerge

from ontobdc.ddock.adapter.system_lock import SystemLock

from ontobdc.ddock.domain.model.system_install import UnpackedPackage

class PackagesHostMovedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.packages_host_moved",
        version="1.0.0",
        name="Packages Host Moved",
        description="Move the contents of src/host of each package into the source folder of the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "Packages Host Moved."},
            "debug_entry": {"en": "Reaching the state Packages Host Moved."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Host dos Pacotes Movido"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # What is still in the src/host of a package was not moved; what left it was.
        return all(
            not self._files_left(package.path / "src" / "host")
            for package in self._pending(context)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        destination: Path = container_path / descriptor.source.local
        without_host: List[str] = []
        moved: int = 0
        package: UnpackedPackage
        for package in self._pending(context):
            host: Path = package.path / "src" / "host"
            if not host.is_dir():
                without_host.append(package.address)
                continue

            moved += len(FolderMerge.merge(host, destination))

        return {
            "resulting_state": SystemInstallProcessState.PACKAGES_HOST_MOVED,
            "files_moved": moved,
            "packages_without_host": without_host,
        }

    @staticmethod
    def _pending(context: CliContextPort) -> List[UnpackedPackage]:
        """
        The packages unpacked in the work folder that the lock does not have yet.
        """
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        pending: List[str] = SystemLock.pending_packages(container_path, descriptor)
        return [
            package
            for package in SystemInstallRequest.packages(context, descriptor.packages)
            if package.address in pending
        ]

    @staticmethod
    def _files_left(host: Path) -> bool:
        return host.is_dir() and any(entry.is_file() for entry in host.rglob("*"))
