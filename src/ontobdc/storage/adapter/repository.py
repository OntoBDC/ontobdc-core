import os
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Tuple, Union
from pathlib import Path
from urllib.parse import unquote, urlparse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.domain.port.graph import (
    StorageGraphModelPort,
    StorageGraphRepositoryPort,
)
from ontobdc.storage.domain.model.graph import StorageGraphModel
from ontobdc.storage.domain.port.repository import StorageContainerRepositoryPort
from ontobdc.shared.adapter.facade import DataContainerFacade
from ontobdc.shared.domain.model.facade import FacadeField, ResourceFacade


class StorageNamespaces:
    """
    Ontology namespaces used by the storage graph, resolved on demand.

    The namespaces come from the ontology configuration, which reads the
    filesystem. Resolving them lazily keeps importing this module free of
    side effects.
    """
    MARKER_DIR_NAME: ClassVar[str] = ".__ontobdc__"

    _namespaces: ClassVar[Dict[str, Namespace]] = {}

    @classmethod
    def ct(cls) -> Namespace:
        return cls._namespace_for("ct")

    @classmethod
    def obdc(cls) -> Namespace:
        return cls._namespace_for("obdc")

    @classmethod
    def _namespace_for(cls, prefix: str) -> Namespace:
        if prefix not in cls._namespaces:
            adapter: OntologyConfigAdapter = OntologyConfigAdapter(
                UnsetProjectRootConfigDataAdapter(),
            )
            cls._namespaces[prefix] = adapter.get_ontology_namespace_by_prefix(prefix)

        return cls._namespaces[prefix]


class StorageContainerRepository(StorageContainerRepositoryPort):
    """
    Repository adapter for a selected storage container.
    """

    def __init__(
        self,
        container_id: str,
    ) -> None:
        self._container_id: str = container_id.strip()
        if not self._container_id:
            raise ValueError("Container id cannot be empty.")

        self._container_subject: Optional[URIRef] = None
        self._container_path: Optional[Path] = None
        self._metadata_path: Optional[Path] = None
        self._graph: Graph = self._load()

    @property
    def id(self) -> str:
        return self._container_id

    @property
    def title(self) -> str:
        return self._graph_value(DCTERMS.title)

    @property
    def description(self) -> str:
        return self._graph_value(StorageNamespaces.ct().description)

    def directory_exists(self) -> bool:
        return self._container_path is not None and self._container_path.is_dir()

    def update(self) -> None:
        self._graph = self._load()

    def write(self, values: Dict[str, str]) -> None:
        """
        Overwrite the given facade fields of the container.
        """
        if self._container_subject is None or self._metadata_path is None:
            raise ValueError(f"Container was not loaded: {self.id}")

        facade: ResourceFacade = DataContainerFacade.read()

        field_identifier: str
        value: str
        for field_identifier, value in values.items():
            declared_field: Optional[FacadeField] = facade.field(field_identifier)
            if declared_field is None:
                raise ValueError(
                    f"The container facade declares no field named "
                    f"'{field_identifier}'."
                )
            if not declared_field.editable:
                raise ValueError(
                    f"The container facade declares '{field_identifier}' as "
                    f"not editable."
                )
            if not isinstance(value, str):
                raise TypeError(
                    f"Value of '{field_identifier}' must be a string, got "
                    f"{type(value).__name__}."
                )

            self._overwrite(URIRef(declared_field.maps_to_property), value)

        self._metadata_path.write_bytes(
            self._graph.serialize(format="turtle", encoding="utf-8")
        )

    def _overwrite(self, predicate: URIRef, value: str) -> None:
        """
        Replace the object of the predicate, keeping its language tag.

        The facade asks for the language tag of the source literal to be
        preserved, so a title written in one language stays tagged as that
        language when its text changes.
        """
        language: Optional[str] = None
        previous: object
        for previous in list(self._graph.objects(self._container_subject, predicate)):
            if isinstance(previous, Literal) and previous.language is not None:
                language = previous.language
            self._graph.remove((self._container_subject, predicate, previous))

        self._graph.add(
            (self._container_subject, predicate, Literal(value, lang=language))
        )

    def delete(self, force: bool = False) -> None:
        raise NotImplementedError

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "directory": self.directory_exists(),
        }

    def _load(self) -> Graph:
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(
            StorageFileLocator.resolve()
        )
        container_value: Optional[Tuple[URIRef, str, str]] = (
            storage_graph.get_container_by_id(self.id)
        )
        if container_value is None:
            raise ValueError(f"Container not found: {self.id}")

        container_subject: URIRef
        container_config_dir: str
        container_storage_file: str
        (
            container_subject,
            container_config_dir,
            container_storage_file,
        ) = container_value

        container_storage_path: Path = Path(container_storage_file)
        if not container_storage_path.is_file():
            raise FileNotFoundError(str(container_storage_path))

        graph: Graph = Graph()
        graph.parse(str(container_storage_path), format="turtle")
        self._container_subject = container_subject
        self._container_path = Path(container_config_dir).parent
        self._metadata_path = container_storage_path
        return graph

    def _graph_value(self, predicate: URIRef) -> str:
        if self._container_subject is None:
            return ""

        value: Any = self._graph.value(self._container_subject, predicate)
        if value is None:
            return ""
        return str(value).strip()


class StorageGraphFileRepository(StorageGraphRepositoryPort):
    def __init__(self, file_path: Union[str, Path]):
        self._file_path: Path = Path(file_path)

    def _get_container_location(self, subject: URIRef) -> Optional[str]:
        location = self.graph.value(subject, PROV.atLocation)
        if location is None:
            return None
        normalized: str = str(location).strip()
        if not normalized:
            return None
        return normalized

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
        for subject, _, _ in self.graph.triples((None, RDF.type, StorageNamespaces.obdc().DataContainer)):
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
            if location_value is None:
                continue
            location_str: str = str(location_value).strip()
            if not location_str:
                continue
            location: Optional[str] = location_str
            if not location:
                continue

            container_path: Path = StorageGraphFileRepository.resolve_location_path(location)
            container_config_dir: Path = container_path / StorageNamespaces.MARKER_DIR_NAME
            container_storage_file: Path = (
                container_config_dir / "container.ttl"
            )
            containers.append((subject, str(container_config_dir), str(container_storage_file)))

        return containers

    def get_container_by_id(
        self,
        container_id: str,
    ) -> Optional[Tuple[URIRef, str, str]]:
        normalized_container_id: str = container_id.strip()
        container_value: Tuple[URIRef, str, str]
        for container_value in self.containers:
            subject: URIRef = container_value[0]
            identifier_values: List[str] = [
                str(identifier).strip()
                for identifier in self.graph.objects(subject, DCTERMS.identifier)
                if str(identifier).strip()
            ]
            if (
                str(subject).strip() == normalized_container_id
                or normalized_container_id in identifier_values
            ):
                return container_value

        return None

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
