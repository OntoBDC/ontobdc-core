
from pathlib import Path
from typing import List, Any
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class RepositoryPort(ABC):
    """
    Base repository port.
    """

    @abstractmethod
    def get_by_id(self, id: str) -> List[Any]:
        """
        Get a file resource by its ID.

        :param id: The ID of the file resource.
        :return: The file resource as a dictionary.
        """
        pass

    @abstractmethod
    def get_all(self) -> List[Any]:
        """
        Get all file resources.

        :return: A list of file resources as dictionaries.
        """
        pass

    @abstractmethod
    def get_by_type(self, type: str) -> List[Any]:
        """
        Get all file resources of a certain type.

        :param type: The type of the file resource.
        :return: A list of file resources as dictionaries.
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a file resource exists.

        :param path: The path of the file resource.
        :return: True if the file resource exists, False otherwise.
        """
        pass


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

