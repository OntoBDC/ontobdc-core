from typing import List

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, FOAF, RDF

from ontobdc.shared.domain.vocabulary import LDP, OBDC
from ontobdc.storage.domain.exception.obdc import StorageObdcFileError
from ontobdc.storage.domain.port.obdc import StorageObdcRemoteModelPort


class StorageObdcRemoteModel(StorageObdcRemoteModelPort):
    """
    How the container is reached over the web, as its ``remote.ttl`` says.

    The ``remote.ttl`` publishes the container as a Linked Data Platform
    container: an ``ldp:BasicContainer`` whose ``foaf:primaryTopic`` is the
    ``obdc:DataContainer`` that keeps its own persistent identifier.
    """

    SCHEMES: tuple = ("http", "https")

    def __init__(self, graph: Graph) -> None:
        self._graph: Graph = graph

    @property
    def graph(self) -> Graph:
        return self._graph

    def addresses(self) -> List[str]:
        return sorted(
            str(subject)
            for subject in self._graph.subjects(RDF.type, LDP.BasicContainer)
            if isinstance(subject, URIRef)
        )

    def validate(self) -> None:
        resources: List[URIRef] = [
            subject
            for subject in self._graph.subjects(RDF.type, LDP.BasicContainer)
            if isinstance(subject, URIRef)
        ]
        if not resources:
            raise StorageObdcFileError("The remote.ttl describes no ldp:BasicContainer.")

        resource: URIRef
        for resource in resources:
            self._validate_resource(resource)

    def _validate_resource(self, resource: URIRef) -> None:
        if not str(resource).lower().startswith(tuple(f"{scheme}://" for scheme in self.SCHEMES)):
            raise StorageObdcFileError(
                f"The ldp:BasicContainer is not an http(s) address: {resource}"
            )

        topics: List[object] = list(self._graph.objects(resource, FOAF.primaryTopic))
        if len(topics) != 1:
            raise StorageObdcFileError(
                f"The ldp:BasicContainer {resource} must have exactly one foaf:primaryTopic."
            )

        topic: object = topics[0]
        if (topic, RDF.type, OBDC.DataContainer) not in self._graph:
            raise StorageObdcFileError(
                f"The foaf:primaryTopic of {resource} is not an obdc:DataContainer: {topic}"
            )

        if next(self._graph.objects(topic, DCTERMS.identifier), None) is None:
            raise StorageObdcFileError(
                f"The obdc:DataContainer {topic} has no dcterms:identifier."
            )

        contained: object
        for contained in self._graph.objects(resource, LDP.contains):
            if not str(contained).lower().startswith(tuple(f"{scheme}://" for scheme in self.SCHEMES)):
                raise StorageObdcFileError(
                    f"ldp:contains of {resource} lists a resource that is not an http(s) address: {contained}"
                )
