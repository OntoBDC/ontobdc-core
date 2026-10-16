from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.storage.domain.model.location import StorageLocation
from ontobdc.storage.domain.port.graph import StorageGraphModelPort


OBDC: Namespace = Namespace("http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#")
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
    def __init__(self, graph: Graph, root_path: Path):
        self._graph: Graph = graph
        # Where the storage root is now (its marker's parent); recorded
        # locations under the root are read relative to it.
        self._root_path: Path = root_path

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

    def recorded_root(self) -> Optional[Path]:
        """
        The location the storage root recorded for itself, if any.
        """
        for subject in self._graph.subjects(RDF.type, OBDC.DataStorage):
            for location in self._graph.objects(subject, PROV.atLocation):
                value: str = str(location).strip()
                if value:
                    return StorageLocation.to_path(value)
        return None

    def resolve_location(self, location: str) -> Path:
        """
        Where a location recorded in this index is now.
        """
        return StorageLocation.rebase(
            StorageLocation.to_path(location),
            self.recorded_root(),
            self._root_path,
        )

    def rebase_to_root(self) -> None:
        """
        Rewrite the recorded locations for the root's current place: the
        root's own location and every container location recorded under it.
        Called when the index is read, before anything is added to it, so the
        locations it holds always agree with each other.
        """
        recorded_root: Optional[Path] = self.recorded_root()
        for subject in list(self._graph.subjects(RDF.type, OBDC.DataStorage)):
            self._graph.remove((subject, PROV.atLocation, None))
            self._graph.add((subject, PROV.atLocation, URIRef(self._root_path.as_uri())))

        for subject in self.iter_container_subjects():
            for location in list(self._graph.objects(subject, PROV.atLocation)):
                recorded: Path = StorageLocation.to_path(str(location).strip())
                current: Path = StorageLocation.rebase(recorded, recorded_root, self._root_path)
                if current != recorded:
                    self._graph.remove((subject, PROV.atLocation, location))
                    self._graph.add((subject, PROV.atLocation, URIRef(current.as_uri())))

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
                return str(self.resolve_location(value))
            return value
        return None
