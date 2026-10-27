from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import SystemInstallRequest
from ontobdc.ddock.plugin.machine.system_install.state import SystemInstallProcessState
from ontobdc.ddock.adapter.zip_archive import ZipArchive

from ontobdc.ddock.adapter.folder_merge import FolderMerge
from ontobdc.ddock.adapter.system_lock import SystemLock
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor

from ontobdc.ddock.domain.model.system_install import ArchiveFiles

class DdockZipExtractedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.ddock_zip_extracted",
        version="1.0.0",
        name="DDock Zip Extracted",
        description="Download the zip of ddock and unpack it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "install", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "DDock Zip Extracted."},
            "debug_entry": {"en": "Reaching the state DDock Zip Extracted."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Zip do DDock Descompactado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # Nothing is left to unpack when the container already has all that ddock puts in it.
        container_path: Path = SystemInstallRequest.container_path(context)
        if SystemLock.ddock_complete(container_path, SystemDescriptors.read(container_path)):
            return True

        return SystemInstallRequest.fetched(SystemInstallRequest.ddock_path(context)) is not None

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        zip_address: str = SystemInstallRequest.ddock_zip(context)
        target: Path = SystemInstallRequest.work_path(context) / "ddock"
        SystemInstallRequest.discard_fetch(target)
        sha256: str = ZipArchive.fetch(zip_address, target)
        descriptor: SystemDescriptor = SystemDescriptors.read(SystemInstallRequest.container_path(context))
        origin: Path = target / descriptor.source
        if not origin.is_dir():
            raise FileNotFoundError(f"The zip of ddock has no folder '{descriptor.source}', the source of system.obdc.")

        SystemInstallRequest.record_fetch(target, ArchiveFiles(zip=zip_address, sha256=sha256, files=FolderMerge.files(origin)))

        return {
            "resulting_state": SystemInstallProcessState.DDOCK_ZIP_EXTRACTED,
            "zip": zip_address,
            "sha256": sha256,
        }
