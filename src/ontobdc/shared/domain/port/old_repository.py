
from pathlib import Path
from rdflib import Graph
from typing import List, Any
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterable


class LoadedStorageGraphPort(ABC):
    @property
    @abstractmethod
    def graph(self) -> Graph:
        """
        The loaded RDF graph.
        """
        ...

    @property
    @abstractmethod
    def file_path(self) -> Path:
        """
        The source file path of the loaded graph.
        """
        ...

    @property
    @abstractmethod
    def containers(self) -> Iterable:
        """
        Iterate over registered containers.
        """
        ...

    @abstractmethod
    def serialize(self, destination: str, format: str = "xml") -> bytes:
        """
        Serialize the loaded graph.
        """
        ...

    @abstractmethod
    def is_valid(self) -> bool:
        """
        Check whether the loaded graph is valid.
        """
        ...


class LoadedStorageContainerCratePort(ABC):
    @property
    @abstractmethod
    def dictionary(self) -> Dict[str, Any]:
        """
        The loaded crate dictionary.
        """
        ...

    @property
    @abstractmethod
    def file_path(self) -> Path:
        """
        The source file path of the loaded crate.
        """
        ...

    @abstractmethod
    def serialize(self, destination: str | Path | None = None) -> None:
        """
        Serialize the loaded crate.
        """
        ...

    @abstractmethod
    def is_valid(self) -> bool:
        """
        Check whether the loaded crate is valid.
        """
        ...

    @abstractmethod
    def refresh(self) -> None:
        ...

    @abstractmethod
    def scan_and_update_dictionary(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def ignored_entity_ids(self) -> list[str]:
        ...

    @abstractmethod
    def remove_ignored_entities(self) -> list[str]:
        ...


class RemoteRepositoryPort(ABC):
    """
    Repository port for remote resources.
    """
    @property
    @abstractmethod
    def url(self) -> 'UrlResourcePort':
        """
        The URL of the remote repository.
        """
        ...

    @abstractmethod
    def serialize(self, format: str = "turtle") -> bytes:
        """
        Serialize the remote repository.
        """
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the repository to a JSON object.
        """
        ...


class RemotePublicRepositoryPort(RemoteRepositoryPort):
    """
    Repository port for remote public resources.
    """
    pass






