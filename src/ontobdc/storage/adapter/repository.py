
import os
import warnings
from pathlib import Path
from rdflib import Graph, URIRef
from rocrate.rocrate import ROCrate
from ontobdc.shared.adapter.config import ConfigDataAdapter
from rdflib.namespace import DCTERMS, PROV, RDF
from typing import List, Any, Dict, Iterable, Optional
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.storage import STORAGE_RDF_BASE_URI, STORAGE_URN_PREFIX
from ontobdc.storage.domain.port.repository import (
    LocalRepositoryPort,
    LoadedStorageGraphPort,
    LoadedStorageContainerCratePort,
)

CT = get_ontology_by_prefix("ct")
CONTAINER_STORAGE_FILE = "storage.ttl"
DATASET_URN_PREFIX = f"{STORAGE_URN_PREFIX}dataset/"


class LoadedStorageGraph(LoadedStorageGraphPort):
    def __init__(self, graph_file: str, format: str = 'turtle'):
        """
        Load the storage graph from the file.

        :param graph_file: The path to the storage graph file.
        :param format: The format of the graph file.
        """
        self._graph_file: Path = Path(graph_file)
        self._graph: Graph = Graph(bind_namespaces="core")
        self._graph.parse(source=graph_file, format=format)

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def file_path(self) -> Path:
        return self._graph_file

    @property
    def containers(self):
        """
        Yields container configurations from the loaded storage graph.
        Skips the root container itself.
        Yields tuples of: (subject, container_config_dir, container_storage_file)
        """
        for s in self._graph.subjects(RDF.type, CT.ContainerDescription):
            identifier = list(self._graph.objects(s, DCTERMS.identifier))
            if identifier and str(identifier[0]) == "urn:ontobdc:storage/local":
                continue

            locations = list(self._graph.objects(s, PROV.atLocation))
            if not locations:
                continue

            loc = str(locations[0])
            
            import os
            # Resolve location path
            if loc.startswith("file://"):
                container_path = loc[7:]
            elif loc.startswith("urn:ontobdc:storage/local"):
                container_path = loc.replace("urn:ontobdc:storage/local", ConfigDataAdapter().root_dir, 1)
            else:
                container_path = loc

            container_config_dir = os.path.join(container_path, ".__ontobdc__")
            container_storage_file = os.path.join(container_config_dir, "storage.ttl")

            yield s, container_config_dir, container_storage_file

    @staticmethod
    def resolve_location_path(location: str) -> Path:
        if location.startswith("file://"):
            return Path(location[7:])
        if location.startswith("urn:ontobdc:storage/local"):
            root_dir = ConfigDataAdapter().root_dir
            if not root_dir:
                raise ValueError("Project root could not be resolved.")
            return Path(location.replace("urn:ontobdc:storage/local", root_dir, 1))
        return Path(location)

    def get_dataset(
        self,
        dataset_ref: Optional[URIRef] = None,
        dataset_location: Optional[str] = None,
    ):
        location_ref: URIRef = self._normalize_dataset_ref(dataset_location) if dataset_location else None
        from ontobdc.storage.adapter.dataset import LocalDatasetRepository

        for _, _, container_storage_file in self.containers:
            container_graph = Graph()
            container_graph.parse(container_storage_file, format="turtle")

            if isinstance(dataset_ref, URIRef) and any(container_graph.triples((dataset_ref, None, None))):
                return LocalDatasetRepository(container_graph, dataset_ref)

            if isinstance(location_ref, URIRef):
                located_dataset_ref = next(container_graph.subjects(PROV.atLocation, location_ref), None)
                if isinstance(located_dataset_ref, URIRef):
                    return LocalDatasetRepository(container_graph, located_dataset_ref)

        return None

    def get_all_datasets(self) -> List[Dict[str, Any]]:
        from rdflib import Literal
        all_datasets: List[Dict[str, Any]] = []

        for subject, _, container_storage_file in self.containers:
            # Obter o container_id
            container_id = None
            for identifier in self.graph.objects(subject, DCTERMS.identifier):
                if isinstance(identifier, Literal):
                    container_id = str(identifier).strip()
                    break
            if not container_id:
                continue

            # Carregar o container graph
            container_graph = Graph()
            container_graph.parse(container_storage_file, format="turtle")

            dataset_refs: List[URIRef] = []
            seen_dataset_refs: set[URIRef] = set()

            for dataset_ref in container_graph.subjects(DCTERMS.isPartOf, None):
                if not isinstance(dataset_ref, URIRef):
                    continue
                if dataset_ref in seen_dataset_refs:
                    continue
                seen_dataset_refs.add(dataset_ref)
                dataset_refs.append(dataset_ref)

            if len(dataset_refs) == 0:
                for dataset_ref in container_graph.objects(None, DCTERMS.hasPart):
                    if not isinstance(dataset_ref, URIRef):
                        continue
                    if dataset_ref in seen_dataset_refs:
                        continue
                    seen_dataset_refs.add(dataset_ref)
                    dataset_refs.append(dataset_ref)

            # Encontrar todos os datasets
            from ontobdc.storage.adapter.dataset import LocalDatasetRepository
            for dataset_ref in dataset_refs:
                dataset_data = LocalDatasetRepository(container_graph, dataset_ref).to_json()
                dataset_data["container_id"] = container_id
                dataset_data["@ref"] = dataset_ref
                all_datasets.append(dataset_data)

        all_datasets.sort(key=lambda item: str(item.get("container_id", "")) + str(item.get("@id", "")))
        return all_datasets

    def serialize(self, destination: str, format: str = "turtle", base: str = STORAGE_RDF_BASE_URI) -> bytes:
        """
        Serialize the loaded graph.
        """
        return self._graph.serialize(destination=destination, format=format)

    def is_valid(self) -> bool:
        try:
            for subject, container_config_dir, container_storage_file in self.containers:
                if not os.path.exists(container_config_dir) or not os.path.isdir(container_config_dir):
                    return False

                if not os.path.exists(container_storage_file) or not os.path.isfile(container_storage_file):
                    return False

                container_graph: Graph = Graph()
                container_graph.parse(container_storage_file, format="turtle")

                root_triples = sorted(
                    (str(predicate), str(obj))
                    for predicate, obj in self.graph.predicate_objects(subject)
                    if predicate in [RDF.type, DCTERMS.identifier, PROV.atLocation, DCTERMS.title, DCTERMS.description]
                )
                container_triples = sorted(
                    (str(predicate), str(obj))
                    for predicate, obj in container_graph.predicate_objects(subject)
                    if predicate in [RDF.type, DCTERMS.identifier, PROV.atLocation, DCTERMS.title, DCTERMS.description]
                )

                if root_triples != container_triples:
                    return False

            return True
        except Exception:
            return False

    def get_root_container(self) -> Optional[URIRef]:
        for s in self._graph.subjects(RDF.type, CT.ContainerDescription):
            identifier = list(self._graph.objects(s, DCTERMS.identifier))
            if identifier and str(identifier[0]) == "urn:ontobdc:storage/local":
                return s

        return None

    def _normalize_dataset_ref(self, dataset_value: str | URIRef) -> URIRef:
        normalized = str(dataset_value).strip()
        if not normalized:
            raise ValueError("Dataset value cannot be empty.")

        from urllib.parse import urlparse
        parsed = urlparse(normalized)
        if isinstance(dataset_value, URIRef) or parsed.scheme:
            return URIRef(normalized)

        return URIRef(f"{DATASET_URN_PREFIX}{normalized}")


class LoadedStorageContainerCrate(LoadedStorageContainerCratePort):
    def __init__(self, crate_file: str):
        """
        Load the storage container crate from the file.

        :param crate_file: The path to the container crate file.
        """
        self._crate_file: Path = Path(crate_file)
        self._crate: ROCrate = ROCrate(source=self.root_dir, gen_preview=False)

    @property
    def dictionary(self) -> Dict[str, Any]:
        return self._crate.metadata.generate()

    @property
    def file_path(self) -> Path:
        return self._crate_file

    @property
    def root_dir(self) -> Path:
        return self._crate_file.parent

    def serialize(self, destination: str | Path | None = None) -> None:
        output_path: Path = Path(destination) if destination else self.root_dir
        if output_path.suffix:
            output_path = output_path.parent
        self._crate.write(output_path)

    def is_valid(self) -> bool:
        try:
            metadata = self.dictionary
            if not isinstance(metadata, dict):
                return False

            if "@graph" not in metadata:
                return False

        except Exception:
            return False

        if not os.path.exists(self.file_path):
            return False

        if not os.path.isfile(self.file_path):
            return False

        graph = metadata.get("@graph")

        return isinstance(graph, list) and len(graph) > 0

    def refresh(self) -> None:
        """
        Refresh the container crate from the file.
        """
        ignored_dataset_paths = self._dataset_paths_to_ignore()

        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root).resolve()
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and not self._is_ignored_dataset_path((root_path / d).resolve(), ignored_dataset_paths)
            ]

            for filename in files:
                if filename.startswith("."):
                    continue
                if filename == self.file_path.name:
                    continue
                if filename == CONTAINER_STORAGE_FILE:
                    continue

                file_path = (root_path / filename).resolve()
                if self._is_ignored_dataset_path(file_path, ignored_dataset_paths):
                    continue
                try:
                    rel_path = file_path.relative_to(self.root_dir)
                except ValueError:
                    continue

                self._crate.add_file(
                    source=None,
                    dest_path=str(rel_path).replace(os.sep, "/"),
                )

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r"No source for .*")
            self.serialize()

    def _dataset_paths_to_ignore(self) -> set[Path]:
        storage_file = self.root_dir / CONTAINER_STORAGE_FILE
        if not storage_file.is_file():
            return set()

        graph = Graph()
        graph.parse(storage_file, format="turtle")

        ignored_paths: set[Path] = set()
        for dataset_ref in graph.subjects(PROV.atLocation, None):
            if not any(graph.triples((dataset_ref, DCTERMS.isPartOf, None))):
                continue

            for location in graph.objects(dataset_ref, PROV.atLocation):
                ignored_paths.add(LoadedStorageGraph.resolve_location_path(str(location)).resolve())

        return ignored_paths

    @staticmethod
    def _is_ignored_dataset_path(path: Path, ignored_dataset_paths: set[Path]) -> bool:
        for ignored_path in ignored_dataset_paths:
            if path == ignored_path or ignored_path in path.parents:
                return True

        return False


class LocalDirectoryRepository(LocalRepositoryPort):
    """
    Repository port for local directory resources.
    """
    def __init__(self, root_path: str):
        self._root_path: Path = Path(root_path)
        
    @property
    def path(self) -> Path:
        return self._root_path

    def list_file(self) -> List[Path]:
        """
        List all files in this dataset.

        :return: A list of Path objects.
        """
        return list(self._iter_file_paths())

    def list_package(self) -> List[Any]:
        """
        List all physical folders in this dataset.

        :return: A list of objects representing the folders.
        """
        packages = []
        if not self._root_path.exists() or not self._root_path.is_dir():
            return packages
            
        for p in self._root_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                packages.append(p.name)
                
        return packages

    def _iter_file_paths(self) -> Iterable[Path]:
        if not self._root_path.exists():
            return []
        if self._root_path.is_file():
            yield self._root_path
            return
        for p in self._root_path.rglob("*"):
            if p.is_file():
                yield p

