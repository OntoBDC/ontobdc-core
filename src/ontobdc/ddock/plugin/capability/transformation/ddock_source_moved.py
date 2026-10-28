from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.ddock_source import DdockSource
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.folder_merge import FolderMerge
from ontobdc.ddock.adapter.system_lock import SystemLock
from ontobdc.ddock.domain.model.system_install import ArchiveFiles


class DdockSourceMovedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.ddock_source_moved",
        version="1.0.0",
        name="DDock Source Moved",
        description="Move the folder of ddock that system.obdc names as source into the container.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "DDock Source Moved."},
            "debug_entry": {"en": "Reaching the state DDock Source Moved."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Fonte do DDock Movida"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # What is still in the source folder of the zip was not moved; what left it was.
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        if SystemLock.ddock_complete(container_path, descriptor):
            return True

        origin: Path = SystemInstallRequest.ddock_path(context) / descriptor.source.local
        return SystemInstallRequest.fetched(SystemInstallRequest.ddock_path(context)) is not None and not any(
            FolderMerge.covers(DdockSource.INCLUDE, name) for name in FolderMerge.files(origin)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemInstallRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        origin: Path = SystemInstallRequest.ddock_path(context) / descriptor.source.local
        destination: Path = container_path / descriptor.source.local
        archive: Optional[ArchiveFiles] = SystemInstallRequest.fetched(SystemInstallRequest.ddock_path(context))
        if archive is not None:
            # The lock lists what ddock put in the container, which is what is moved.
            SystemInstallRequest.record_fetch(
                SystemInstallRequest.ddock_path(context),
                archive.model_copy(
                    update={"files": [name for name in archive.files if FolderMerge.covers(DdockSource.INCLUDE, name)]}
                ),
            )

        moved: List[Path] = FolderMerge.merge(origin, destination, DdockSource.INCLUDE)

        return {
            "resulting_state": SystemInstallProcessState.DDOCK_SOURCE_MOVED,
            "source": str(destination),
            "files_moved": len(moved),
        }
