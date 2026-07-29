
from pathlib import Path
from rdflib import Literal
from typing import Optional
from rdflib.graph import Graph
from abc import ABC, abstractmethod
from rdflib.namespace import Namespace


class OntologyConfigPort(ABC):
    """
    Port interface representing access to the application's ontology configuration, namespaces, and content.
    """
    @abstractmethod
    def get_ontology_namespace_by_prefix(self, prefix: str) -> Optional[Namespace]:
        """
        Get ontology namespace by prefix.
        """
        pass

    @abstractmethod
    def get_ontology_path(self, prefix: str, type: str = "ns") -> str:
        """
        Get the path to the ontology file based on prefix and type.
        """
        pass

    @abstractmethod
    def get_ontology_content(self, prefix: str, type: str = "ns") -> Graph:
        """
        Get the parsed RDF graph of the ontology.
        """
        pass

    @abstractmethod
    def as_literal(self, value: str) -> Optional[Literal]:
        """
        Convert a string value to an RDF Literal.
        """
        pass


class OntologyRepositoryPort(ABC):
    @property
    @abstractmethod
    def graph(self) -> Graph:
        ...

    @property
    @abstractmethod
    def graph_path(self) -> Path:
        ...

    @abstractmethod
    def save(self) -> None:
        ...

    @abstractmethod
    def load(self) -> None:
        ...
