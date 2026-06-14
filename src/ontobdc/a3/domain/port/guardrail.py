
from typing import Any, Dict
from abc import ABC, abstractmethod


class JsonSchemaGuardrailPort(ABC):
    @property
    @abstractmethod
    def uri(self) -> str:
        pass

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        pass

    @property
    @abstractmethod
    def ontology_uri(self) -> str:
        pass

    @property
    @abstractmethod
    def shape_id(self) -> str:
        pass

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> None:
        pass