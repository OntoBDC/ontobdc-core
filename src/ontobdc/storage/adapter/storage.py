
import os
from uuid import uuid4
from pathlib import Path
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

    # def serialize(self) -> str:
    #     rdfxml: str = super().serialize()
    #     return rdfxml

    def add(self, storage_path: str, save_action: callable = None) -> None:
        if not self._load_index():
            raise ValueError("Failed to load storage index")

        storage_path = storage_path.strip()
        if storage_path.startswith(get_root_dir()):
            storage_path = storage_path[len(get_root_dir()):]

        storage_path: str = storage_path.strip('/')
        master_container = URIRef(f"{self.container_id}")
        child_identifier: str = f"{str(uuid4())}/{storage_path}"
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



