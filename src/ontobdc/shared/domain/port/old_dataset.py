


from abc import abstractmethod, ABC
from typing import Optional, Dict, Any
from ontobdc.context.domain.port.remote import DatasetFacadeResourcePort, LinksetDatapackageResourcePort
from ontobdc.shared.domain.model.entity import EntityMetadata
from ontobdc.shared.domain.port.repository import ContainerRepositoryPort, LocalRepositoryPort
from ontobdc.shared.domain.port.briefcase import RemoteBriefcaseRepositoryPort

class RemoteDatasetRepositoryPort(RemoteBriefcaseRepositoryPort, ABC):
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
    def linkset_datapackage(self) -> LinksetDatapackageResourcePort:
        """
        The linkset datapackage resource for this remote dataset.
        """
        ...

    @property
    @abstractmethod
    def facade(self) -> DatasetFacadeResourcePort:
        """
        The facade of the remote dataset.
        """
        ...


    @abstractmethod
    def download(self) -> RemoteDatasetRepositoryPort:
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


class RemoteDatasetCapabilityVisitorPort(RemoteDatasetCapabilityPort):
    """
    Port for visitor patterns that require access to the remote dataset repository.
    """
    @abstractmethod
    def visit(self, capability: RemoteDatasetCapability) -> RemoteDatasetCapability:
        """
        Visit the capability and return the capability instance.
        """
        ...
