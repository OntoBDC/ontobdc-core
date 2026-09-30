from abc import ABC, abstractmethod
from typing import Any, Dict


class StorageContainerPort(ABC):
    """
    Domain contract for a storage container.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        ...

    @property
    @abstractmethod
    def title(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def directory_exists(self) -> bool:
        ...

    @abstractmethod
    def update(self) -> None:
        ...

    @abstractmethod
    def delete(self, force: bool = False) -> None:
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        ...
