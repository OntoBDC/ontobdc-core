
from abc import abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Iterable
from ontobdc.core.domain.port.repository import RepositoryPort
from ontobdc.module.resource.domain.port.entity import (
    FilesystemPort,
    FolderPort,
    MediaTypePort,
)


class DocumentRepositoryPort(RepositoryPort):
    """
    Repository port for document resources.
    """

    @property
    @abstractmethod
    def filesystem(self) -> FilesystemPort:
        """
        Get the filesystem configuration.

        :return: The filesystem configuration as a FilesystemPort.
        """
        pass

    @property
    @abstractmethod
    def path_folders(self) -> List[FolderPort]:
        """
        Get the list of folders in the path.

        :return: The list of folders in the path as FolderPort.
        """
        pass


class FileRepositoryPort(DocumentRepositoryPort):
    """
    Repository port for file resources.
    """

    def get_by_id(self, id: str) -> List[Any]:
        """
        Get a file resource by its ID.

        :param id: The ID of the file resource.
        :return: The file resource as a dictionary.
        """
        return self.get_by_name(name=id)

    def get_by_type(self, type: str) -> List[Any]:
        """
        Get all file resources of a certain type.

        :param type: The type of the file resource.
        :return: A list of file resources as dictionaries.
        """
        return self.get_by_mimetype(mimetype=type)

    @abstractmethod
    def get_by_name(self, name: str) -> List[Any]:
        """
        Get a file resource by its name.

        :param name: The name of the file resource.
        :return: The file resource as a dictionary.
        """
        pass

    @abstractmethod
    def get_by_mimetype(self, mimetype: Any) -> List[Any]:
        """
        Get all file resources of a certain mimetype.

        :param mimetype: The mimetype of the file resource.
        :return: A list of file resources as dictionaries.
        """
        pass

    @abstractmethod
    def get_by_media_types(self, media_types: List[MediaTypePort]) -> List[Any]:
        """
        Get all file resources that match any of the given media types.

        :param media_types: List of MediaTypePort instances to filter by.
        :return: A list of file resources as dictionaries.
        """
        pass

    @abstractmethod
    def iter_file_paths(self) -> Iterable[Path]:
        """
        Iterate over all physical file paths for this repository.

        :return: An iterator over Paths for all files in all folders and subfolders.
        """
        pass

    @abstractmethod
    def open_file(self, path: str, mode: str = "r") -> Any:
        """
        Open a file from the repository.

        :param path: The path to the file (absolute or relative to repo root).
        :param mode: The mode to open the file in (default 'r').
        :return: A file-like object.
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if a file exists in the repository.

        :param path: The path to the file.
        :return: True if the file exists, False otherwise.
        """
        pass

    @abstractmethod
    def rename(self, src: str, dst: str) -> None:
        """
        Rename a file in the repository.

        :param src: The source path.
        :param dst: The destination path.
        """
        pass

    @abstractmethod
    def get_json(self, path: str) -> Any:
        """
        Get the JSON content of a file.

        :param path: The relative path to the file.
        :return: The JSON content as a dictionary or list, or None if not found.
        """
        pass


class DatasetRepositoryPort(DocumentRepositoryPort):
    """
    Repository port for dataset resources.
    """
    pass
