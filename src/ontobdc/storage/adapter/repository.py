
import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union
from urllib.parse import unquote, urlparse

from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import DCTERMS, PROV, RDF
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.domain.model.graph import StorageGraphModel
from ontobdc.storage.domain.port.graph import StorageGraphRepositoryPort, StorageGraphModelPort


ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    UnsetProjectRootConfigDataAdapter(),
)
CT: Namespace = ontology_adapter.get_ontology_namespace_by_prefix("ct")
OBDC: Namespace = ontology_adapter.get_ontology_namespace_by_prefix("obdc")
MARKER_DIR_NAME = ".__ontobdc__"


class StorageGraphFileRepository(StorageGraphRepositoryPort):
    def __init__(self, file_path: Union[str, Path]):
        self._file_path: Path = Path(file_path)

    def _get_container_location(self, subject: URIRef) -> Optional[str]:
        location = self.graph.value(subject, PROV.atLocation)
        normalized = str(location or "").strip()
        return normalized or None

    @staticmethod
    def resolve_location_path(location: str) -> Path:
        parsed = urlparse(location)
        if parsed.scheme and parsed.scheme != "file":
            raise ValueError(
                f"Unsupported container location scheme: {parsed.scheme}"
            )

        raw_path = unquote(parsed.path if parsed.scheme else location)
        if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2:
            if raw_path[2] == ":":
                raw_path = raw_path[1:]

        return Path(raw_path).expanduser().resolve()

    @property
    def file_path(self) -> Path:
        return self._file_path

    def load(self) -> StorageGraphModel:
        if not self._file_path.exists():
            raise FileNotFoundError(str(self._file_path))

        graph: Graph = Graph()
        graph.parse(str(self._file_path), format="turtle")
        return StorageGraphModel(graph)

    def save(self, storage_graph: StorageGraphModel) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        serialized: bytes = storage_graph.graph.serialize(format="turtle", encoding="utf-8")
        self._file_path.write_bytes(serialized)


class LoadedStorageGraph:
    def __init__(self, file_path: Union[str, Path], format: str = "turtle"):
        self._repository: StorageGraphRepositoryPort = StorageGraphFileRepository(file_path)
        self._storage_graph: StorageGraphModelPort = self._repository.load()

    @property
    def graph(self) -> Graph:
        return self._storage_graph.graph

    @property
    def storage_graph(self) -> StorageGraphModel:
        return self._storage_graph

    @property
    def containers(self) -> Iterable[Tuple[URIRef, str, str]]:
        containers: List[Tuple[URIRef, str, str]] = []
        for subject, _, _ in self.graph.triples((None, RDF.type, OBDC.DataContainer)):
            if not isinstance(subject, URIRef):
                continue

            identifier_values: List[str] = [
                str(identifier).strip()
                for identifier in self.graph.objects(subject, DCTERMS.identifier)
                if str(identifier).strip()
            ]

            if "urn:ontobdc:storage/local" in identifier_values:
                continue

            location_value = self.graph.value(subject, PROV.atLocation)
            location: Optional[str] = str(location_value or "").strip() or None
            if not location:
                continue

            container_path: Path = StorageGraphFileRepository.resolve_location_path(location)
            container_config_dir: Path = container_path / MARKER_DIR_NAME
            container_storage_file: Path = (
                container_config_dir / "container.ttl"
            )
            containers.append((subject, str(container_config_dir), str(container_storage_file)))

        return containers

    @property
    def file_path(self) -> Path:
        return self._repository.file_path

    def serialize(
        self,
        destination: str,
        format: str = "turtle",
    ) -> bytes:
        return self.graph.serialize(destination=destination, format=format)

    def is_valid(self) -> bool:
        try:
            for subject, container_config_dir, container_storage_file in self.containers:
                if not os.path.isdir(container_config_dir):
                    return False

                if not os.path.isfile(container_storage_file):
                    return False

                container_graph: Graph = Graph()
                container_graph.parse(container_storage_file, format="turtle")
                # normalize_ct_namespace_to_http(container_graph)

                root_triples: List[Tuple[str, str]] = sorted(
                    (str(predicate), str(obj))
                    for predicate, obj in self.graph.predicate_objects(subject)
                    if predicate in [RDF.type, DCTERMS.identifier, PROV.atLocation, DCTERMS.title, DCTERMS.description]
                )
                container_triples: List[Tuple[str, str]] = sorted(
                    (str(predicate), str(obj))
                    for predicate, obj in container_graph.predicate_objects(subject)
                    if predicate in [RDF.type, DCTERMS.identifier, PROV.atLocation, DCTERMS.title, DCTERMS.description]
                )

                if root_triples != container_triples:
                    return False

            return True
        except Exception:
            return False
