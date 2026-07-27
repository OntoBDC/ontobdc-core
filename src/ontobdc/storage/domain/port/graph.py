
from pathlib import Path
from rdflib import Graph, URIRef
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class StorageGraphModelPort(ABC):
    @property
    @abstractmethod
    def graph(self) -> Graph:
        ...

    @abstractmethod
    def iter_container_subjects(self) -> List[URIRef]:
        ...

    @abstractmethod
    def list_containers(self) -> List[Dict[str, Optional[str]]]:
        ...

    @abstractmethod
    def subject_predicate_objects(self, subject: URIRef) -> List[Tuple[Any, Any]]:
        ...

    @abstractmethod
    def add_subject_predicate_objects(
        self,
        subject: URIRef,
        predicate_objects: List[Tuple[Any, Any]],
    ) -> None:
        ...



class StorageGraphRepositoryPort(ABC):
    @abstractmethod
    def load(self) -> StorageGraphModelPort:
        ...

    @abstractmethod
    def save(self, storage_graph: StorageGraphModelPort) -> None:
        ...

    @property
    @abstractmethod
    def file_path(self) -> Path:
        ...