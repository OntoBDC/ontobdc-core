
import os
import shutil
from pathlib import Path
from rdflib.namespace import RDF, OWL
from urllib.parse import urlparse, unquote
from rdflib import Graph, Namespace, URIRef, Literal
from ontobdc.cli import get_config_dir, get_root_dir
from ontobdc.storage.adapter.icdd import ICDDIndexAdapter
from ontobdc.storage.adapter.crate import CrateStorageAdapter


class StorageIndexAdapter(ICDDIndexAdapter):

    _xml_base = f"urn:ontobdc-org:storage/"
    DCTERMS = Namespace("http://purl.org/dc/terms/")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    INDEX_FILE = "storage.rdf"

    def __init__(self):
        self._index_path = os.path.join(get_config_dir(), self.INDEX_FILE)
        self._container_id: str = None
        self._index_graph: Graph = None

    @classmethod
    def create(cls) -> 'StorageIndexAdapter':
        # Create the directory if it does not exist
        container_path: str = os.path.join(get_config_dir(), "tmp", "storage_container")
        os.makedirs(container_path, exist_ok=True)

        storage_index_adapter: StorageIndexAdapter = cls()

        index_adapter: ICDDIndexAdapter = ICDDIndexAdapter.create(container_path, cls._xml_base)
        storage_index_adapter._container_id = index_adapter.container_id
        storage_index_adapter._index_graph = index_adapter._graph

        storage_index_adapter._graph.bind("dcterms", cls.DCTERMS)
        storage_index_adapter._graph.add((URIRef(f"{storage_index_adapter.container_id}"), RDF.type, cls.DCTERMS.Location))
        storage_index_adapter._graph.add((URIRef(f"{storage_index_adapter.container_id}"), cls.DCTERMS.title, Literal('The Main Storage Index', lang="en")))

        ct = Namespace(storage_index_adapter._get_namespace("ct"))
        storage_index_adapter._graph.add((cls.DCTERMS.description, OWL.equivalentClass, ct.ContainerDescription))

        os.rmdir(container_path)
        os.rmdir(os.path.dirname(container_path))

        return storage_index_adapter

    @property
    def xml_base(self) -> str:
        return StorageIndexAdapter._xml_base

    def _load_index(self) -> bool:
        if isinstance(self._index_graph, Graph):
            return True

        if not os.path.isfile(self._index_path):
            return False

        self._index_graph = Graph()
        self._index_graph.parse(self._index_path)

        if self._container_id is None:
            for s in self._index_graph.subjects(RDF.type, ICDDIndexAdapter.CT.ContainerDescription):
                self._container_id = str(s)
                break

        if self._container_id is None:
            for o in self._index_graph.objects(predicate=StorageIndexAdapter.DCTERMS.isPartOf):
                self._container_id = str(o)
                break

        return isinstance(self._index_graph, Graph)

    def add(self, storage_path: str, save_action: callable = None) -> None:
        if not self._load_index():
            raise ValueError("Failed to load storage index")

        storage_path = storage_path.strip()
        if storage_path.startswith(get_root_dir()):
            storage_path = storage_path[len(get_root_dir()):]

        storage_path: str = storage_path.strip('/')
        master_container = URIRef(f"{self.container_id}")
        child_identifier: str = f"{self.container_id}/{storage_path}"
        child_dataset = URIRef(child_identifier)

        self._graph.add((child_dataset, RDF.type, StorageIndexAdapter.DCTERMS.Dataset))
        self._graph.add((child_dataset, StorageIndexAdapter.DCTERMS.identifier, Literal(child_identifier)))
        self._graph.add((child_dataset, StorageIndexAdapter.DCTERMS.title, Literal(f"The storage dataset for {storage_path}",  lang="en")))

        self._graph.bind("prov", StorageIndexAdapter.PROV)
        file_uri: str = Path(os.path.join(get_root_dir(), storage_path)).resolve().as_uri()
        self._graph.add((child_dataset, StorageIndexAdapter.PROV.atLocation, URIRef(file_uri)))

        self._graph.add((master_container, StorageIndexAdapter.DCTERMS.hasPart, child_dataset))
        self._graph.add((child_dataset, StorageIndexAdapter.DCTERMS.isPartOf, master_container))

        if type(save_action).__name__ == 'method':
            save_action()
        else:
            self.save()

        if not CrateStorageAdapter.is_valid(storage_path):
            CrateStorageAdapter.create(storage_path)

    def _find_dataset_ref(self, dataset_id: str):
        dcterms = StorageIndexAdapter.DCTERMS

        for s in set(self._graph.subjects(dcterms.identifier, None)):
            for o in self._graph.objects(s, dcterms.identifier):
                if str(o) == dataset_id:
                    return s

        candidates = []
        for s in set(self._graph.subjects(RDF.type, dcterms.Dataset)):
            candidates.append(s)
        base = StorageIndexAdapter._xml_base.rstrip("/") + "/"
        for s in candidates:
            ss = str(s)
            if ss == dataset_id:
                return s
            if ss.endswith("/" + dataset_id) or ss.endswith(dataset_id):
                return s
            if dataset_id.startswith(base) and ss == dataset_id:
                return s

        return None

    def has_dataset(self, dataset_id: str) -> bool:
        if not self._load_index():
            raise ValueError("Failed to load storage index")
        dataset_id = (dataset_id or "").strip()
        if not dataset_id:
            return False
        return self._find_dataset_ref(dataset_id) is not None

    def _resolve_dataset_path(self, dataset_ref) -> tuple[str, Path]:
        locs = [str(o) for o in self._graph.objects(dataset_ref, StorageIndexAdapter.PROV.atLocation)]
        if not locs:
            raise ValueError(f"Dataset {dataset_ref} has no prov:atLocation")

        loc = locs[0]
        if not loc.startswith("file://"):
            raise ValueError(f"Dataset {dataset_ref} has unsupported location: {loc}")

        parsed = urlparse(loc)
        dataset_path = Path(unquote(parsed.path))
        return loc, dataset_path

    def remove(self, dataset_id: str, save_action: callable = None) -> bool:
        if not self._load_index():
            raise ValueError("Failed to load storage index")

        dataset_id = (dataset_id or "").strip()
        if not dataset_id:
            raise ValueError("dataset_id is required")

        dcterms = StorageIndexAdapter.DCTERMS
        dataset_ref = self._find_dataset_ref(dataset_id)
        if dataset_ref is None:
            return False

        locations = [str(o) for o in self._graph.objects(dataset_ref, StorageIndexAdapter.PROV.atLocation)]

        for container in list(self._graph.objects(dataset_ref, dcterms.isPartOf)):
            self._graph.remove((container, dcterms.hasPart, dataset_ref))
            self._graph.remove((dataset_ref, dcterms.isPartOf, container))

        self._graph.remove((dataset_ref, None, None))
        self._graph.remove((None, None, dataset_ref))

        if type(save_action).__name__ == "method":
            save_action()
        else:
            self.save()

        for loc in locations:
            if not loc.startswith("file://"):
                continue
            parsed = urlparse(loc)
            dataset_path = Path(unquote(parsed.path))
            icdd_dir = dataset_path / ".__icdd__"
            if icdd_dir.exists():
                shutil.rmtree(icdd_dir, ignore_errors=True)

        return True

    def refresh(self, dataset_id: str | None = None, save_action: callable = None) -> int:
        if not self._load_index():
            raise ValueError("Failed to load storage index")

        dcterms = StorageIndexAdapter.DCTERMS

        datasets = []
        if dataset_id:
            dataset_ref = self._find_dataset_ref(dataset_id.strip())
            if dataset_ref is None:
                raise ValueError(f"Dataset not found: {dataset_id}")
            datasets = [dataset_ref]
        else:
            datasets = list(set(self._graph.subjects(RDF.type, dcterms.Dataset)))

        changed = False
        refreshed = 0

        for ds in datasets:
            loc, dataset_path = self._resolve_dataset_path(ds)
            if not dataset_path.exists():
                raise FileNotFoundError(f"Dataset path does not exist for {ds}: {dataset_path}")

            changed_by_refresh = CrateStorageAdapter.refresh(str(dataset_path))
            if changed_by_refresh:
                refreshed += 1

            canonical_uri = dataset_path.resolve().as_uri()
            if loc != canonical_uri:
                self._graph.remove((ds, StorageIndexAdapter.PROV.atLocation, URIRef(loc)))
                self._graph.add((ds, StorageIndexAdapter.PROV.atLocation, URIRef(canonical_uri)))
                changed = True

        if changed:
            if type(save_action).__name__ == "method":
                save_action()
            else:
                self.save()

        return refreshed
