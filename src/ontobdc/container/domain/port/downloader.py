from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class RemoteFileDownloadError(Exception):
    """
    The remote file could not be downloaded.
    """


class RemoteFileDownloaderPort(ABC):
    @abstractmethod
    def download(self, url: str, destination: Path, api_token: Optional[str] = None) -> int:
        """
        Save the file at ``url`` as ``destination`` and return its size in
        bytes. An existing ``destination`` is never overwritten. ``api_token``,
        when given, is sent as a bearer token.

        :raises RemoteFileDownloadError: when the file cannot be downloaded.
        """
        ...
