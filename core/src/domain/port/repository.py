
from abc import ABC, abstractmethod
from typing import List, Dict, Any


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