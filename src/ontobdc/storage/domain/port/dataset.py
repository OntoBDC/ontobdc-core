
from abc import abstractmethod, ABC
from typing import Optional, Dict, Any
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort, LocalRepositoryPort


class DatasetRepositoryPort(LocalRepositoryPort, ABC):
    """
    Repository port for dataset resources.
    """
    @property
    @abstractmethod
    def id(self) -> str:
        """
        The identifier of the dataset.
        """
        ...

    @property
    @abstractmethod
    def container(self) -> Optional[ContainerRepositoryPort]:
        """
        The container repository associated with this dataset.
        """
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the repository to a JSON object.

        :return: A JSON object with the repository information.
        """
        ...

