import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import ClassVar, Optional

from ontobdc.container.domain.port.downloader import (
    RemoteFileDownloadError,
    RemoteFileDownloaderPort,
)


class UrllibRemoteFileDownloader(RemoteFileDownloaderPort):
    """
    Downloads a remote file over ``http`` or ``https`` with the standard
    library, straight to disk, so a large file never sits in memory.
    """

    TIMEOUT_SECONDS: ClassVar[float] = 30.0
    CHUNK_SIZE: ClassVar[int] = 64 * 1024

    def download(self, url: str, destination: Path, api_token: Optional[str] = None) -> int:
        if destination.exists():
            raise RemoteFileDownloadError(
                f"The file already exists and was not overwritten: {destination}"
            )

        headers = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

        partial: Path = destination.with_name(destination.name + ".part")
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(
                request, timeout=self.TIMEOUT_SECONDS
            ) as response, open(partial, "wb") as target:
                shutil.copyfileobj(response, target, self.CHUNK_SIZE)
            partial.replace(destination)
        except urllib.error.HTTPError as error:
            raise RemoteFileDownloadError(
                f"The server answered HTTP {error.code} ({error.reason})."
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RemoteFileDownloadError(
                f"The file could not be downloaded: {error}"
            ) from error
        finally:
            if partial.exists():
                partial.unlink()

        return destination.stat().st_size


class PyodideRemoteFileDownloader(RemoteFileDownloaderPort):
    """
    Placeholder for the browser: Pyodide has no sockets of its own, so the
    standard library cannot download there. The browser-side download is
    not implemented yet.
    """

    def download(self, url: str, destination: Path, api_token: Optional[str] = None) -> int:
        raise RemoteFileDownloadError(
            "Downloading a remote file is not implemented in Pyodide yet."
        )


class RemoteFileDownloader:
    """
    Resolves the file downloader for the runtime in use.
    """

    @staticmethod
    def for_runtime() -> RemoteFileDownloaderPort:
        if sys.platform == "emscripten":
            return PyodideRemoteFileDownloader()

        return UrllibRemoteFileDownloader()
