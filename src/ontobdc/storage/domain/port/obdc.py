from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from rdflib import Graph


class StorageObdcRemoteModelPort(ABC):
    @property
    @abstractmethod
    def graph(self) -> Graph:
        ...

    @abstractmethod
    def addresses(self) -> List[str]:
        """
        The http(s) addresses of the ``ldp:BasicContainer`` resources the
        ``remote.ttl`` publishes.
        """
        ...

    @abstractmethod
    def validate(self) -> None:
        """
        :raises StorageObdcFileError: when the graph does not describe the
            remote access to a ``obdc:DataContainer``.
        """
        ...


class StorageObdcRepositoryPort(ABC):
    """
    Repository contract for ``.obdc`` files.

    An ``.obdc`` file is a zip archive with another extension.
    """

    @abstractmethod
    def read_remote(self, obdc_path: Path) -> StorageObdcRemoteModelPort:
        """
        Open the ``.obdc`` file and return the model of its ``remote.ttl``.

        :raises StorageObdcFileError: when the file cannot be read as such.
        """
        ...
