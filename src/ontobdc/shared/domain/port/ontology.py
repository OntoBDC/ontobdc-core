from abc import ABC, abstractmethod
from typing import List
from pathlib import Path

from rdflib.graph import Graph


class OntologyLibraryPort(ABC):
    """
    The ontologies available to the application, each addressed by its IRI.

    An ontology is named by the IRI it is published at, never by a short
    prefix or a local table: whoever needs an ontology states which one, and
    an ontology that is not available is an error naming that IRI.
    """

    @abstractmethod
    def path(self, iri: str) -> Path:
        """
        The file of the ontology published at ``iri`` (or of the ontology
        that declares the term ``iri``, ``...#Term``).

        Raises:
            FileNotFoundError: no ontology is available at ``iri``.
        """
        ...

    @abstractmethod
    def graph(self, iri: str) -> Graph:
        """
        The parsed ontology published at ``iri``.

        Raises:
            FileNotFoundError: no ontology is available at ``iri``.
        """
        ...

    @abstractmethod
    def graph_with_imports(self, iri: str) -> Graph:
        """
        The ontology published at ``iri`` merged with every ontology it
        imports (``owl:imports``), transitively.

        Raises:
            FileNotFoundError: the ontology, or one it imports, is not
                available.
        """
        ...

    @abstractmethod
    def iris(self) -> List[str]:
        """
        The IRI of every available ontology.
        """
        ...


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
