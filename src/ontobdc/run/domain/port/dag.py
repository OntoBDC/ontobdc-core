
from rdflib import Graph
from typing import Any, Dict
from abc import ABC, abstractmethod
from ontobdc.shared.domain.resource.capability import QueryCapability


class DagParametersEvaluatorPort(ABC):
    """
    Port for evaluating parameters for the acyclic graph.
    """

    @property
    @abstractmethod
    def graph(self) -> Graph:
        """
        Returns the RDF graph of the DAG.
        """
        ...

    @abstractmethod
    def add_query_capability(self, capability: QueryCapability) -> None:
        """
        Adds the capability to the acyclic graph.
        """
        ...

    @abstractmethod
    def missing(self) -> Dict[str, Any]:
        """
        Returns the missing parameters for the acyclic graph.
        """
        ...

    @abstractmethod
    def evaluate(self) -> bool:
        """
        Evaluates the parameters for the acyclic graph.
        """
        ...
