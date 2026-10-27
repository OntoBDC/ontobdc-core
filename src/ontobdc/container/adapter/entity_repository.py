from pathlib import Path
from typing import Any, Dict, List

from ontobdc.container.adapter.entity_csv_repository import EntityCsvRepository
from ontobdc.container.adapter.entity_turtle_repository import EntityTurtleRepository
from ontobdc.container.domain.port.entity import EntityRepositoryPort


class ContainerEntityRepository(EntityRepositoryPort):
    """
    The repository of the entities of a container: each dataset is kept the
    way it has its data, as a CSV spreadsheet or as Turtle files. The CSV is
    preferred when a dataset has both.
    """

    CONTEXT_KEY: str = "entity_repository"

    def __init__(self) -> None:
        self._csv: EntityRepositoryPort = EntityCsvRepository()
        self._turtle: EntityRepositoryPort = EntityTurtleRepository()

    @classmethod
    def provide(cls, context: Any) -> None:
        """
        Hands the context this repository, unless the caller already handed
        it one of its own.
        """
        if context.get_parameter_value(cls.CONTEXT_KEY) is None:
            context.set_parameter_value(cls.CONTEXT_KEY, cls())

    def _of(self, dataset_path: Path) -> EntityRepositoryPort:
        return (
            self._turtle
            if not self._csv.data_source_exists(dataset_path)
            and self._turtle.data_source_exists(dataset_path)
            else self._csv
        )

    def data_source_exists(self, dataset_path: Path) -> bool:
        return self._csv.data_source_exists(dataset_path) or self._turtle.data_source_exists(dataset_path)

    def create_data_source(self, dataset_path: Path) -> Path:
        return self._csv.create_data_source(dataset_path)

    def data_source_path(self, dataset_path: Path) -> Path:
        return self._of(dataset_path).data_source_path(dataset_path)

    def columns(self, dataset_path: Path) -> List[str]:
        return self._of(dataset_path).columns(dataset_path)

    def add_columns(self, dataset_path: Path, columns: List[str]) -> None:
        self._of(dataset_path).add_columns(dataset_path, columns)

    def rows(self, dataset_path: Path) -> Dict[str, Dict[str, str]]:
        return self._of(dataset_path).rows(dataset_path)

    def upsert_rows(self, dataset_path: Path, rows: List[Dict[str, Any]]) -> None:
        self._of(dataset_path).upsert_rows(dataset_path, rows)

    def delete_rows(self, dataset_path: Path, global_ids: List[str]) -> None:
        self._of(dataset_path).delete_rows(dataset_path, global_ids)
