from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from rdflib import Graph

from ontobdc.core.domain.resource.entity import Entity


class EntityStoragePort(ABC):
    @staticmethod
    @abstractmethod
    def get(unique_name: str) -> Entity:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def create(unique_name: str) -> Entity:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def exists(unique_name: str) -> bool:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def entity_path(unique_name: str) -> Optional[Path]:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def entity_config() -> Graph:
        raise NotImplementedError
