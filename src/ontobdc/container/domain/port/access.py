from abc import ABC, abstractmethod
from typing import Optional


class RemoteAccessError(Exception):
    """
    The remote container cannot be accessed with the credentials given.
    """


class RemoteAccessProbePort(ABC):
    @abstractmethod
    def probe(self, url: str, api_token: Optional[str] = None) -> None:
        """
        Check that ``url`` answers a request made with ``api_token``.

        :raises RemoteAccessError: when it does not answer with success.
        """
        ...
