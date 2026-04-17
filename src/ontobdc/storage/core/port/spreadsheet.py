
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class TableSchemaPort(ABC):
    @property
    @abstractmethod
    def fields(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class SpreadsheetPort(ABC):
    @property
    @abstractmethod
    def fields(self) -> List[Dict[str, Any]]:
        ...

    @property
    @abstractmethod
    def data(self) -> List[Dict[str, Any]]:
        ...

    @classmethod
    @abstractmethod
    def create(cls, target: Any, schema: TableSchemaPort) -> Any:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def validate(cls, target: Any, schema: TableSchemaPort) -> bool:
        raise NotImplementedError
