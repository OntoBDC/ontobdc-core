from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.adapter.remote_file import RemoteFileDownloader
from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.domain.port.downloader import RemoteFileDownloaderPort
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState


class RemoteFileAvailableCapability(TransactionCapability):
    """
    Downloads the file of a remote OntoBDC Container into the current directory.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "remote_file_available"
        ),
        version="1.0.0",
        name="Remote File Available",
        description=(
            "Download the file of a remote OntoBDC Container into the "
            "current directory."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "remote", "download"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The remote container file is available.",
            },
            "debug_entry": {
                "en": "Downloading the remote container file.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.REMOTE_FILE_AVAILABLE.label(lang)

    def description(self, lang: str = "en") -> str:
        return RemoteContainerProcessState.REMOTE_FILE_AVAILABLE.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        url_value: Any = context.get_parameter_value("remote_url")
        if not isinstance(url_value, str) or not RemoteContainerUrl.is_valid(url_value):
            return False

        try:
            return RemoteContainerUrl.destination(
                url_value, context.get_parameter_value("remote_download_dir")
            ).is_file()
        except OSError:
            return False

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        url_value: Any = context.get_parameter_value("remote_url")
        if not isinstance(url_value, str) or not url_value.strip():
            raise ValueError("The remote container URL is missing from the command context.")

        url: str = url_value.strip()
        destination: Path = RemoteContainerUrl.destination(
            url, context.get_parameter_value("remote_download_dir")
        )
        api_token: Any = context.get_parameter_value("remote_api_token")

        downloader: RemoteFileDownloaderPort = RemoteFileDownloader.for_runtime()
        size: int = downloader.download(
            url, destination, api_token if isinstance(api_token, str) else None
        )

        return {
            "resulting_state": RemoteContainerProcessState.REMOTE_FILE_AVAILABLE,
            "url": url,
            "path": str(destination),
            "size": size,
        }
