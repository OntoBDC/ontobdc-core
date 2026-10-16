from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.obdc import StorageObdcRepository
from ontobdc.storage.domain.port.obdc import StorageObdcRemoteModelPort

from ontobdc.container.adapter.remote_file import RemoteFileDownloader
from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.domain.port.downloader import RemoteFileDownloaderPort
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState


class ContainerFilesDownloadedCapability(TransactionCapability):
    """
    Downloads each file of the remote container, one at a time, into the
    local container the connection just created.

    Which files to fetch is not discovered from the remote yet: ``FILES``
    declares them here, as paths relative to whichever address of the
    remote container answers first.
    """

    FILES: ClassVar[List[str]] = [
        '.__ontobdc__/.remote_ro-crate-metadata.json',
        '.__ontobdc__/.remote_container.ttl'
    ]

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_files_downloaded"
        ),
        version="1.0.0",
        name="Container Files Downloaded",
        description=(
            "Download each file of the remote container into the local "
            "container."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "remote", "download"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "Every remote container file was downloaded.",
            },
            "debug_entry": {
                "en": "Downloading the remote container files.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_FILES_DOWNLOADED.label(lang)

    def description(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.CONTAINER_FILES_DOWNLOADED.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path: Path = self._container_path(context)
        return all(
            (container_path / file_path).is_file() for file_path in self.FILES
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = self._container_path(context)
        address: str = self._first_address(context)
        api_token_value: Any = context.get_parameter_value("remote_api_token")
        api_token: Any = api_token_value if isinstance(api_token_value, str) else None

        downloader: RemoteFileDownloaderPort = RemoteFileDownloader.for_runtime()
        downloaded: List[str] = []
        file_path: str
        for file_path in self.FILES:
            file_url: str = f"{address.rstrip('/')}/{file_path.lstrip('/')}"
            destination: Path = container_path / file_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            downloader.download(file_url, destination, api_token)
            downloaded.append(str(destination))

        return {
            "resulting_state": RemoteContainerProcessState.CONTAINER_FILES_DOWNLOADED,
            "container_path": str(container_path),
            "files": downloaded,
        }

    @staticmethod
    def _container_path(context: CliContextPort) -> Path:
        container_path: Any = context.get_parameter_value("container_path")
        if isinstance(container_path, str) and container_path.strip():
            return Path(container_path)

        url: Any = context.get_parameter_value("remote_url")
        download_dir: Any = context.get_parameter_value("remote_download_dir")
        return RemoteContainerUrl.destination(url, download_dir).parent

    @staticmethod
    def _first_address(context: CliContextPort) -> str:
        url_value: Any = context.get_parameter_value("remote_url")
        path: Path = RemoteContainerUrl.destination(
            str(url_value).strip(), context.get_parameter_value("remote_download_dir")
        )
        remote: StorageObdcRemoteModelPort = StorageObdcRepository().read_remote(path)
        addresses: List[str] = list(remote.addresses())
        if not addresses:
            raise ValueError("The remote.ttl publishes no address to download files from.")

        return addresses[0]
