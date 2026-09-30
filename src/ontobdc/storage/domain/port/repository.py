from abc import ABC, abstractmethod
from typing import Any, Dict


class StorageContainerRepositoryPort(ABC):
    """
    Repository contract for container persistence.
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
    def write(self, values: Dict[str, str]) -> None:
        """
        Overwrite the given facade fields of the container.

        Values are keyed by the field identifier the facade declares, which
        is the name a user recognises. A field the facade does not declare,
        or declares as not editable, is rejected.
        """
        ...

    @abstractmethod
    def delete(self, force: bool = False) -> None:
        ...

    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        ...
