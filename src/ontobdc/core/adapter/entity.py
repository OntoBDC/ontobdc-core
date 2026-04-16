
import os
from pathlib import Path
from typing import List, Any
from ontobdc.cli import get_config_dir
from ontobdc.core.domain.resource.entity import Entity
from ontobdc.core.domain.port.entity import EntityRepositoryPort


class EntityFileRepositoryAdapter(EntityRepositoryPort):
    def __init__(self, entity: Entity):
        self._root_path: Path = Path(os.path.join(get_config_dir(), "payload", "data", *entity.package, entity.title))
        os.makedirs(self._root_path, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._root_path

    def get_by_id(self, id: str) -> List[Any]:
        """
        Get a file resource by its ID.

        :param id: The ID of the file resource.
        :return: The file resource as a dictionary.
        """
        return []

    def get_all(self) -> List[Path]:
        return list(map(Path, os.listdir(self._root_path)))

    def exists(self, path: Path) -> bool:
        return (self._root_path / path).exists()

    def get_by_type(self, type_filter: str) -> List[Any]:
        """
        Get all file resources of a certain type.

        :param type_filter: The type of the file resource.
        :return: A list of file resources as dictionaries.
        """
        raise NotImplementedError()
