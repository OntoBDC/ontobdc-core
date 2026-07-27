
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from ontobdc.shared.facade.port.dataset import DatasetRepositoryPort
from ontobdc.shared.facade.port.container import ContainerRepositoryPort


class ResourcePort(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def location(self) -> str:
        ...

    @abstractmethod
    def exists(self) -> bool:
        ...

    @abstractmethod
    def is_text(self) -> bool:
        ...

    @abstractmethod
    def is_binary(self) -> bool:
        ...

    @abstractmethod
    def is_multimedia(self) -> bool:
        ...

    @abstractmethod
    def is_dict(self) -> bool:
        ...


class UrlResourcePort(ResourcePort):
    @property
    def location(self) -> str:
        return self.url

    @property
    @abstractmethod
    def url(self) -> str:
        ...

    @abstractmethod
    def download(self) -> None:
        ...


class FileResourcePort(ResourcePort):
    @property
    def location(self) -> str:
        return str(self.path)

    @property
    @abstractmethod
    def container(self) -> Optional[ContainerRepositoryPort]:
        ...

    @property
    @abstractmethod
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        ...

    @property
    @abstractmethod
    def path(self) -> Path:
        ...

    @property
    @abstractmethod
    def mimetype(self) -> str:
        ...

    @abstractmethod
    def rename(self, dst: Path) -> None:
        ...

    @abstractmethod
    def delete(self) -> None:
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the file resource to a JSON object.

        :return: A JSON object with the file resource information.
        """
        ...

    @abstractmethod
    def write(self, dataset: 'DatasetRepositoryPort') -> None:
        """
        Write the file resource to the dataset.

        :param dataset: The target dataset (DatasetRepositoryPort).
        """
        ...

    @property
    @abstractmethod
    def content(self) -> str:
        ...


class TextFileResourcePort(FileResourcePort):
    pass


class FileResourceStrategyPort(ABC):
    @abstractmethod
    def supports(self, resource_path: Path) -> bool:
        ...

    @abstractmethod
    def load(self, resource_path: Path) -> FileResourcePort:
        ...


