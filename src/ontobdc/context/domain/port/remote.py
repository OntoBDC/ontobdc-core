
from rdflib import Graph, URIRef
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class RemoteResourcePort(ABC):
    @property
    @abstractmethod
    def url(self) -> str:
        pass


class RemoteFileResourcePort(RemoteResourcePort):
    pass


class LinksetDatapackageResourcePort(RemoteFileResourcePort):
    @abstractmethod
    def get_resource_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_all_resources(self) -> List[Dict[str, Any]]:
        pass


class DatasetFacadeResourcePort(RemoteFileResourcePort):
    """
    Port for dataset facade resources (usually dataset.ttl).
    """
    @property
    @abstractmethod
    def graph(self) -> Graph:
        """
        The graph instance of the dataset facade resource.
        """
        ...

    @abstractmethod
    def serialize(self, format: str = "turtle") -> bytes:
        """
        Serialize the dataset facade resource to a bytes.

        :param format: The format to serialize to (default: turtle).
        :return: The serialized bytes.
        """
        ...


class RemoteResourceLoaderPort(ABC):
    @abstractmethod
    def get_entity_instances(self, repo: 'RemoteDatasetRepositoryPort', entity_class: URIRef) -> Dict[str, Dict[str, Any]]:
        pass