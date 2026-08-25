
from dataclasses import dataclass
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from rdflib.namespace import DCTERMS, PROV, RDF
from typing import Any, Dict, List, Optional, Tuple
from rdflib import Graph, Literal, Namespace, URIRef
from ontobdc.storage.domain.port.graph import StorageGraphModelPort

OBDC: Namespace = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")
CT: Namespace = Namespace("http://standards.iso.org/iso/21597/-1/ed-1/en/Container#")


@dataclass(frozen=True)
class StorageContainerView:
    id: Optional[str]
    title: Optional[str]
    description: Optional[str]
    location: Optional[str]

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
        }


class StorageGraphModel(StorageGraphModelPort):
    def __init__(self, graph: Graph):
        self._graph: Graph = graph

    @property
    def graph(self) -> Graph:
        return self._graph

    def iter_container_subjects(self) -> List[URIRef]:
        subjects: List[URIRef] = []
        for subject, _, _ in self._graph.triples((None, RDF.type, OBDC.DataContainer)):
            if isinstance(subject, URIRef):
                subjects.append(subject)
        return subjects

    def list_containers(self) -> List[Dict[str, Optional[str]]]:
        containers: List[Dict[str, Optional[str]]] = []
        for subject in self.iter_container_subjects():
            container_view: StorageContainerView = StorageContainerView(
                id=self._get_first_literal(subject, DCTERMS.identifier),
                title=self._get_first_as_str(subject, DCTERMS.title),
                description=self._get_first_as_str(subject, CT.description),
                location=self._get_first_location(subject),
            )
            containers.append(container_view.to_dict())
        return containers

    def subject_predicate_objects(self, subject: URIRef) -> List[Tuple[Any, Any]]:
        predicate_objects: List[Tuple[Any, Any]] = []
        for predicate, obj in self._graph.predicate_objects(subject):
            predicate_objects.append((predicate, obj))
        return predicate_objects

    def add_subject_predicate_objects(
        self,
        subject: URIRef,
        predicate_objects: List[Tuple[Any, Any]],
    ) -> None:
        for predicate, obj in predicate_objects:
            self._graph.add((subject, predicate, obj))

    def _get_first_as_str(self, subject: URIRef, predicate: URIRef) -> Optional[str]:
        for obj in self._graph.objects(subject, predicate):
            return str(obj)
        return None

    def _get_first_literal(self, subject: URIRef, predicate: URIRef) -> Optional[str]:
        for obj in self._graph.objects(subject, predicate):
            if isinstance(obj, Literal):
                return str(obj).strip()
            return str(obj).strip()
        return None

    def _get_first_location(self, subject: URIRef) -> Optional[str]:
        for obj in self._graph.objects(subject, PROV.atLocation):
            value: str = str(obj).strip()
            if value.startswith("file://"):
                parsed = urlparse(value)
                return url2pathname(unquote(parsed.path))
            return value
        return None
