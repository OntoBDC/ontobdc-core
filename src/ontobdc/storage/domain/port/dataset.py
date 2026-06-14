
from abc import abstractmethod, ABC
from typing import Any, Dict, Optional, TYPE_CHECKING
from ontobdc.context.domain.resource.remote import EntityMetadata
from ontobdc.context.domain.port.remote import LinksetDatapackageResourcePort, DatasetFacadeResourcePort
from ontobdc.storage.domain.port.repository import LocalRepositoryPort, RemoteRepositoryPort

if TYPE_CHECKING:
    from ontobdc.context.adapter.remote import RemoteDatasetCapability


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
    def container(self) -> Optional['ContainerRepositoryPort']:
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


class RemoteDatasetRepositoryPort(RemoteRepositoryPort, ABC):
    """
    Repository port for remote dataset resources.
    """
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """
        The capabilities of the dataset repository.
        """
        ...

    @property
    @abstractmethod
    def entities(self) -> Dict[str, EntityMetadata]:
        """
        The entities provided by the dataset repository.
        """
        ...

    @property
    @abstractmethod
    def linkset_datapackage(self) -> 'LinksetDatapackageResourcePort':
        """
        The linkset datapackage resource for this remote dataset.
        """
        ...

    @property
    @abstractmethod
    def facade(self) -> 'DatasetFacadeResourcePort':
        """
        The facade of the remote dataset.
        """
        ...


    @abstractmethod
    def download(self) -> 'RemoteDatasetRepositoryPort':
        """
        Download the dataset from the remote URL.
        :return: The downloaded dataset repository.
        """
        ...


class RemoteDatasetCapabilityPort(ABC):
    """
    Port for capabilities that require access to the remote dataset repository.
    """
    @property
    @abstractmethod
    def remote_dataset_repo(self) -> RemoteDatasetRepositoryPort:
        """
        The remote dataset repository instance.
        """
        ...


class EntityQueryCapabilityVisitablePort(ABC):
    """
    Port for capabilities that can accept visitors.
    """
    @abstractmethod
    def accept(self, visitor: 'RemoteDatasetCapabilityVisitorPort') -> Any:
        """
        Accept a visitor and return the result.
        """
        ...


class RemoteDatasetCapabilityVisitorPort(RemoteDatasetCapabilityPort):
    """
    Port for visitor patterns that require access to the remote dataset repository.
    """
    @abstractmethod
    def visit(self, capability: 'RemoteDatasetCapability') -> 'RemoteDatasetCapability':
        """
        Visit the capability and return the capability instance.
        """
        ...

