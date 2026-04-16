
import os
import shutil
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlparse, unquote
from rdflib.namespace import RDF, OWL, XSD
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

    def remove(self, dataset_id: str, save_action: callable = None) -> bool:
        if not self._load_index():
            raise ValueError("Failed to load storage index")

        dataset_id = (dataset_id or "").strip()
        if not dataset_id:
            raise ValueError("dataset_id is required")

        dcterms = StorageIndexAdapter.DCTERMS
        dataset_ref = None

        for s in set(self._graph.subjects(dcterms.identifier, None)):
            for o in self._graph.objects(s, dcterms.identifier):
                if str(o) == dataset_id:
                    dataset_ref = s
                    break
            if dataset_ref is not None:
                break

        if dataset_ref is None:
            candidates = []
            for s in set(self._graph.subjects(RDF.type, dcterms.Dataset)):
                candidates.append(s)
            base = StorageIndexAdapter._xml_base.rstrip("/") + "/"
            for s in candidates:
                ss = str(s)
                if ss == dataset_id:
                    dataset_ref = s
                    break
                if ss.endswith("/" + dataset_id) or ss.endswith(dataset_id):
                    dataset_ref = s
                    break
                if dataset_id.startswith(base) and ss == dataset_id:
                    dataset_ref = s
                    break

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
