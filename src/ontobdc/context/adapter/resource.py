
from rdflib import Graph
from ontobdc.context.domain.port.remote import DatasetFacadeResourcePort


class DatasetFacadeResource(DatasetFacadeResourcePort):
    """
    Adapter for dataset facade resources (usually dataset.ttl).
    """
    def __init__(self, url: str, graph: Graph):
        self._url: str = url
        self._graph: Graph = graph
    
    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def url(self) -> str:
        return self._url

    def serialize(self, format: str = "turtle") -> bytes:
        return self._graph.serialize(format=format)