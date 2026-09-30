from typing import Any, Dict

from ontobdc.storage.domain.port.container import StorageContainerPort
from ontobdc.storage.domain.port.repository import StorageContainerRepositoryPort


class StorageContainer(StorageContainerPort):
    """
    Storage container model backed by an abstract repository.
    """

    def __init__(self, repository: StorageContainerRepositoryPort) -> None:
        self._repository: StorageContainerRepositoryPort = repository

    @property
    def id(self) -> str:
        return self._repository.id

    @property
    def title(self) -> str:
        return self._repository.title

    @property
    def description(self) -> str:
        return self._repository.description

    def directory_exists(self) -> bool:
        return self._repository.directory_exists()

    def update(self) -> None:
        self._repository.update()

    def delete(self, force: bool = False) -> None:
        self._repository.delete(force=force)

    def to_json(self) -> Dict[str, Any]:
        return self._repository.to_json()
