
from pathlib import Path
from rdflib import Graph
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterable


class LocalRepositoryPort(ABC):
    """
    Repository port for local resources.
    """
    @property
    @abstractmethod
    def path(self) -> Path:
        """
        The root path of the repository.
        """
        pass

    @abstractmethod
    def list_file(self) -> List[Path]:
        """
        Get all physical file paths for this repository.

        :return: A list of Paths for all files in all folders and subfolders.
        """
        pass

    @abstractmethod
    def list_package(self) -> List[Any]:
        """
        List all packages for this repository.

        :return: A list of package objects representing packages.
        """
        pass


class ContainerRepositoryPort(ABC):
    """
    Repository port for container resources.
    """
    @property
    @abstractmethod
    def id(self) -> str:
        """
        The identifier of the container.

        :return: The identifier of the container.
        """
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        """
        The title of the container.

        :return: The title of the container.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """
        The description of the container.

        :return: The description of the container.
        """
        ...

    @abstractmethod
    def container_exists(self) -> bool:
        """
        Check if the container exists.

        :return: True if the container exists, False otherwise.
        """
        ...

    @abstractmethod
    def save(self):
        """
        Save the repository to the storage file.
        """
        ...

    @abstractmethod
    def delete(self, force: bool = False) -> None:
        """
        Delete the container from the graph.

        :param force: Whether to force the deletion, even if the container has datasets.
        """
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the repository to a JSON object.

        :return: A JSON object with the repository information.
        """
        ...


class RootContainerRepositoryPort(ContainerRepositoryPort):
    """
    Repository port for root container resources.
    """
    pass


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

