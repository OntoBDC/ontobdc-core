from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class EntityRepositoryPort(ABC):
    """
    Where the rows of an entity are physically kept, inside a dataset.

    Whoever owns the storage of the entities (a CSV file, a spreadsheet,
    a database) implements this contract and hands it to the process that
    writes them. A row is a mapping from the identifier of a facade field to
    its value; the column ``global_id`` identifies it.
    """

    @abstractmethod
    def data_source_exists(self, dataset_path: Path) -> bool:
        """
        Whether the dataset already has the data source of the entity.
        """
        ...

    @abstractmethod
    def create_data_source(self, dataset_path: Path) -> Path:
        """
        Create the data source with the ``global_id`` column only and return
        where it is.
        """
        ...

    @abstractmethod
    def data_source_path(self, dataset_path: Path) -> Path:
        """
        Where the data source of the dataset is.

        Raises:
            FileNotFoundError: the dataset has no data source.
        """
        ...

    @abstractmethod
    def columns(self, dataset_path: Path) -> List[str]:
        """
        The columns the data source has, in order.
        """
        ...

    @abstractmethod
    def add_columns(self, dataset_path: Path, columns: List[str]) -> None:
        """
        Append the given columns, which the data source does not have yet.
        """
        ...

    @abstractmethod
    def rows(self, dataset_path: Path) -> Dict[str, Dict[str, str]]:
        """
        The rows the data source holds, by ``global_id``; each maps every
        column to its text ("" where the row has nothing).
        """
        ...

    @abstractmethod
    def upsert_rows(self, dataset_path: Path, rows: List[Dict[str, Any]]) -> None:
        """
        Write the rows, replacing the ones that have the same ``global_id``.
        """
        ...

    @abstractmethod
    def delete_rows(self, dataset_path: Path, global_ids: List[str]) -> None:
        """
        Remove the rows that have the given ``global_id``. A ``global_id``
        the data source does not hold is ignored.
        """
        ...
