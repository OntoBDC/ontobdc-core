import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.ddock.adapter.ddock_source import DdockSource
from ontobdc.ddock.adapter.folder_merge import FolderMerge
from ontobdc.ddock.adapter.github_zip import GitHubZipAddress
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.adapter.zip_archive import ZipArchive
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.domain.model.system_install import ArchiveFiles
from ontobdc.ddock.plugin.machine.system_update.machine import SystemUpdateRequest
from ontobdc.ddock.plugin.machine.system_update.state import SystemUpdateProcessState


class DdockSourceRefreshedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.ddock.plugin.capability.transformation.target.ddock_source_refreshed",
        version="1.0.0",
        name="DDock Source Refreshed",
        description="Download the ddock of the repository system.obdc names again and replace the source folder of the container with it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["ddock", "update", "system"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "DDock Source Refreshed."},
            "debug_entry": {"en": "Reaching the state DDock Source Refreshed."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Fonte do DDock Atualizada"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        # Replacing the source folder is not a fact kept on disk that says it
        # was this run that did it, so each update replaces it once.
        return SystemUpdateRequest.ddock_refreshed(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = SystemUpdateRequest.container_path(context)
        descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        remote: str = descriptor.source.remote or GitHubZipAddress.DEFAULT_REPOSITORY
        zip_address: Optional[str] = GitHubZipAddress.resolve(remote)
        if zip_address is None:
            raise ValueError(f"The ddock repository {remote} has no zip of its master or its main branch.")

        target: Path = SystemUpdateRequest.ddock_path(context)
        SystemUpdateRequest.discard_fetch(target)
        sha256: str = ZipArchive.fetch(zip_address, target)
        origin: Path = target / descriptor.source.local
        if not origin.is_dir():
            raise FileNotFoundError(f"The zip of ddock has no folder '{descriptor.source.local}', the source of system.obdc.")

        SystemUpdateRequest.record_fetch(
            target,
            ArchiveFiles(
                zip=zip_address,
                sha256=sha256,
                files=[name for name in FolderMerge.files(origin) if FolderMerge.covers(DdockSource.INCLUDE, name)],
            ),
        )

        destination: Path = container_path / descriptor.source.local
        shutil.rmtree(destination, ignore_errors=True)
        moved: List[Path] = FolderMerge.merge(origin, destination, DdockSource.INCLUDE)
        context.set_parameter_value(SystemUpdateRequest.DDOCK_REFRESHED_KEY, True)

        return {
            "resulting_state": SystemUpdateProcessState.DDOCK_SOURCE_REFRESHED,
            "zip": zip_address,
            "sha256": sha256,
            "source": str(destination),
            "files_moved": len(moved),
        }
