
import os
import sys
from ontobdc.context.adapter.resource import DatasetFacadeResource
import requests
import tempfile
import importlib.util
from urllib.parse import urljoin, urlparse
from ontobdc.context.adapter.remote import LinksetDatapackageResource, LinksetDatapackageResourcePort
from ontobdc.context.domain.port.remote import DatasetFacadeResourcePort
from ontobdc.storage.domain.port.dataset import (
    RemoteDatasetRepositoryPort, 
    DatasetRepositoryPort
)
from ontobdc.context.domain.resource.remote import RemoteCapabilityMetadata, EntityMetadata
from ontobdc.storage.domain.port.resource import UrlResourcePort
from rdflib import Graph, URIRef, Literal
from typing import List, Any, Dict, Optional
from pathlib import Path
from rdflib.namespace import DCTERMS, PROV, RDF
from ontobdc.storage.adapter.resource import LocalFileResource, TripleFileResource
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.storage.domain.port.repository import RemotePublicRepositoryPort
from ontobdc.storage.adapter.repository import LocalDirectoryRepository

CT = get_ontology_by_prefix("ct")
DCAT = get_ontology_by_prefix("dcat")
OBDC = get_ontology_by_prefix("obdc")
VOID = get_ontology_by_prefix("void")


class RemotePublicRepository(RemotePublicRepositoryPort):
    def __init__(self, url: UrlResourcePort, graph: Graph):
        self._url: UrlResourcePort = url
        self._graph: Graph = graph

    @property
    def url(self) -> str:
        return self._url.url

    def serialize(self, format: str = "turtle") -> bytes:
        return self._graph.serialize(format=format)

    def to_json(self) -> Dict[str, Any]:
        return {}


class RemotePublicDatasetRepository(RemotePublicRepository, RemoteDatasetRepositoryPort):
    def __init__(self, dataset_url: UrlResourcePort):
        target_dataset: Graph = Graph()
        target_dataset.parse(dataset_url.url, format="turtle")

        # Find the dataset URIRef
        dataset_ref: Optional[URIRef] = None
        for s in target_dataset.subjects(RDF.type, DCAT.Dataset):
            dataset_ref = s
            break
        if not dataset_ref:
            raise ValueError("No dcat:Dataset found in the remote turtle file.")

        self._dataset: URIRef = dataset_ref

        super().__init__(dataset_url, target_dataset)

    @property
    def url(self) -> UrlResourcePort:
        # Remote datasets don't have a local path
        return self._url

    @property
    def id(self) -> str:
        return str(self._dataset)

    @property
    def location(self) -> str:
        return self._url

    @property
    def container(self) -> Any:
        container_refs: List[URIRef] = list(self._graph.objects(self._dataset, DCTERMS.isPartOf))
        if container_refs:
            return str(container_refs[0])

        return None

    @property
    def linkset_datapackage(self) -> 'LinksetDatapackageResourcePort':
        return LinksetDatapackageResource(self.url.url)

    @property
    def facade(self) -> DatasetFacadeResourcePort:
        """
        The dataset facade resource.
        """
        return DatasetFacadeResource(self.url.url, self._graph)

    @property
    def entities(self) -> Dict[str, EntityMetadata]:
        entities: Dict[str, EntityMetadata] = {}

        # Find all documents/datasets that have a void:class defined
        for doc_ref in self._graph.subjects(VOID['class'], None):
            for class_uri in self._graph.objects(doc_ref, VOID['class']):
                if not isinstance(class_uri, URIRef):
                    continue

                entity_uri: Optional[URIRef] = self._graph.value(doc_ref, DCTERMS.type, None)
                if not entity_uri:
                    continue

                # Get title of the entity (class) instead of the document
                title_dict: Dict[str, str] = {}
                for title in self._graph.objects(entity_uri, DCTERMS.title):
                    if isinstance(title, Literal):
                        lang = title.language or "en"
                        title_dict[lang] = title.value

                # Get description of the entity (class) instead of the document
                desc_dict: Dict[str, str] = {}
                for desc in self._graph.objects(entity_uri, DCTERMS.description):
                    if isinstance(desc, Literal):
                        lang = desc.language or "en"
                        desc_dict[lang] = desc.value

                entities[str(entity_uri)] = EntityMetadata(
                    class_uri=class_uri,
                    title=title_dict,
                    description=desc_dict,
                    document_ref=doc_ref
                )

        return entities

    @property
    def capabilities(self) -> Dict[str, RemoteCapabilityMetadata]:
        capabilities: Dict[str, RemoteCapabilityMetadata] = {}

        # Find all QueryCapability individuals
        for cap_ref in self._graph.subjects(RDF.type, OBDC.QueryCapability):
            # Get identifier (required)
            id_literals: List[Literal] = list(self._graph.objects(cap_ref, DCTERMS.identifier))
            if not id_literals:
                continue
            cap_id: str = str(id_literals[0])

            # Get title
            title_dict: Dict[str, str] = {}
            for title in self._graph.objects(cap_ref, DCTERMS.title):
                if isinstance(title, Literal):
                    lang = title.language or "en"
                    title_dict[lang] = title.value

            # Get description
            desc_dict: Dict[str, str] = {}
            for desc in self._graph.objects(cap_ref, DCTERMS.description):
                if isinstance(desc, Literal):
                    lang = desc.language or "en"
                    desc_dict[lang] = desc.value

            capabilities[cap_id] = RemoteCapabilityMetadata(
                identifier=cap_id,
                title=title_dict,
                description=desc_dict,
                document_ref=cap_ref,
            )

        return capabilities

    def download(self) -> RemoteDatasetRepositoryPort:
        return self

    def load_capability(self, capability_id: str) -> Any:
        """
        Load a capability module from the remote dataset, downloading all resources.
        """
        # First, derive the datapackage.json URL from the dataset URL
        parsed_url: str = urlparse(self.url.url)
        path: Path = Path(parsed_url.path)

        # Replace dataset.ttl (or similar) with linkset/datapackage.json
        new_path: Path = path.parent / "linkset" / "datapackage.json"

        # Reconstruct the URL
        datapackage_url: str = parsed_url._replace(path=str(new_path)).geturl()

        # Download datapackage.json
        response = requests.get(datapackage_url)
        response.raise_for_status()
        datapackage: Dict[str, Any] = response.json()

        # Find the resource for our capability
        capability_resource: Optional[Dict[str, Any]] = None
        for resource in datapackage.get("resources", []):
            if resource.get("name") == capability_id:
                capability_resource = resource
                break

        if not capability_resource:
            raise ValueError(f"Capability '{capability_id}' not found in datapackage")

        # Download all resources to temp dir, preserving directory structure
        temp_root = Path(tempfile.mkdtemp(prefix="ontobdc_remote_"))
        for resource in datapackage.get("resources", []):
            resource_path_str = resource.get("path")
            if not resource_path_str:
                continue

            # Create full destination path
            resource_path: Path = Path(resource_path_str)
            dest_path: Path = temp_root / resource_path

            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the resource
            resource_url = urljoin(datapackage_url, resource_path_str)
            resource_response = requests.get(resource_url)
            resource_response.raise_for_status()

            # Write the file
            with open(dest_path, "wb") as f:
                f.write(resource_response.content)

        # Now find the capability file and import it
        capability_path_str: str = capability_resource.get("path")
        if not capability_path_str:
            raise ValueError(f"Capability resource has no path specified")

        temp_capability_file = temp_root / capability_path_str

        # Import the module
        spec = importlib.util.spec_from_file_location(
            capability_id.replace(".", "_"),
            temp_capability_file
        )
        if spec is None or spec.loader is None:
            raise ImportError("Failed to create module spec")

        module = importlib.util.module_from_spec(spec)
        sys.modules[capability_id.replace(".", "_")] = module
        spec.loader.exec_module(module)

        return module

    def add_resource(self, resource: LocalFileResource | TripleFileResource) -> None:
        # Can't add resources to a remote dataset
        raise NotImplementedError("Can't add resources to a remote dataset.")

    def to_json(self) -> Dict[str, Any]:
        data = {'@id': str(self._dataset), 'url': self.url}

        container_refs: List[URIRef] = list(self._graph.objects(self._dataset, DCTERMS.isPartOf))
        if container_refs:
            data['container'] = str(container_refs[0])

        title_list: List[Literal] = list(self._graph.objects(self._dataset, DCTERMS.title))
        if title_list:
            data['title'] = {title.language: title.value for title in title_list}

        return data


class LocalDatasetRepository(LocalDirectoryRepository, DatasetRepositoryPort):
    def __init__(self, graph: Graph, dataset: URIRef):
        self._dataset: URIRef = dataset
        self._graph: Graph = graph  # Store the graph reference for capabilities
        self._data: Dict[str, Any] = {'@id': str(self._dataset)}
        super().__init__(self._load(graph))

    @classmethod
    def create(
        cls,
        container_graph: Graph,
        container_subject: URIRef,
        dataset_ref: URIRef,
        dataset_location: str,
        container_storage_file: Path
    ) -> "LocalDatasetRepository":
        """
        Creates a new dataset within a container. Modifies the container's graph,
        creates the physical directory on disk, and serializes the updated graph.
        """
        # Validate if dataset already exists
        if any(container_graph.triples((dataset_ref, None, None))):
            raise ValueError(f"Dataset '{dataset_ref}' already exists in graph.")
        if next(container_graph.subjects(PROV.atLocation, URIRef(dataset_location)), None) is not None:
            raise ValueError(f"Dataset location '{dataset_location}' already exists in graph.")

        from ontobdc.storage.adapter.repository import LoadedStorageGraph
        dataset_path = LoadedStorageGraph.resolve_location_path(dataset_location)

        if dataset_path.exists():
            raise ValueError(f"Dataset path already exists: {dataset_path}")

        # Add triples to container graph
        container_graph.add((dataset_ref, RDF.type, CT.ContainerDescription))
        container_graph.add((dataset_ref, RDF.type, DCAT.Dataset))
        container_graph.add((dataset_ref, RDF.type, CT.Folder))
        container_graph.add((container_subject, DCTERMS.hasPart, dataset_ref))
        container_graph.add((dataset_ref, DCTERMS.isPartOf, container_subject))
        container_graph.add((dataset_ref, PROV.atLocation, URIRef(dataset_location)))

        # Create physical directory
        dataset_path.mkdir(parents=True, exist_ok=False)

        # Create dataset's dataset.ttl
        dataset_graph = Graph()
        dataset_graph.bind("dcterms", DCTERMS)
        dataset_graph.bind("prov", PROV)
        dataset_graph.bind("dcat", DCAT)
        dataset_graph.bind("ct", CT)
        
        for p, o in container_graph.predicate_objects(dataset_ref):
            dataset_graph.add((dataset_ref, p, o))
            
        dataset_index_file = dataset_path / "dataset.ttl"
        dataset_graph.serialize(destination=str(dataset_index_file), format="turtle")

        # Persist graph changes
        container_graph.serialize(destination=str(container_storage_file), format="turtle")

        return cls(container_graph, dataset_ref)

    @property
    def id(self) -> str:
        return self._data['@id']

    @property
    def location(self) -> str:
        if 'location' not in self._data:
            raise ValueError(f"Dataset {self.id} has no location")

        return self._data['location']

    @property
    def container(self) -> Any:
        # Avoid circular imports and complex instantiation if not immediately needed
        # It's meant to return an instance of ContainerRepositoryPort
        return self._data.get('container')

    @property
    def capabilities(self) -> Dict[str, RemoteCapabilityMetadata]:
        capabilities: Dict[str, RemoteCapabilityMetadata] = {}

        # Find all QueryCapability individuals in the graph
        for cap_ref in self._graph.subjects(RDF.type, OBDC.QueryCapability):
            # Get identifier (required)
            id_literals: List[Literal] = list(self._graph.objects(cap_ref, DCTERMS.identifier))
            if not id_literals:
                continue
            cap_id: str = str(id_literals[0])

            # Get title
            title_dict: Dict[str, str] = {}
            for title in self._graph.objects(cap_ref, DCTERMS.title):
                if isinstance(title, Literal):
                    lang = title.language or "en"
                    title_dict[lang] = title.value

            # Get description
            desc_dict: Dict[str, str] = {}
            for desc in self._graph.objects(cap_ref, DCTERMS.description):
                if isinstance(desc, Literal):
                    lang = desc.language or "en"
                    desc_dict[lang] = desc.value

            # Get version
            version: Optional[str] = None
            version_literals = list(self._graph.objects(cap_ref, DCTERMS.version))
            if version_literals:
                version = str(version_literals[0])

            # Get output schema
            output_schema: Optional[URIRef] = None
            output_refs = list(self._graph.objects(cap_ref, OBDC.outputContains))
            if output_refs and isinstance(output_refs[0], URIRef):
                output_schema = output_refs[0]

            # Create metadata object
            metadata = RemoteCapabilityMetadata(
                identifier=cap_id,
                title=title_dict,
                description=desc_dict,
                version=version,
                output_schema=output_schema
            )
            capabilities[cap_id] = metadata

        return capabilities

    def to_json(self) -> Dict[str, Any]:
        return self._data

    def list_resource(self) -> List[LocalFileResource]:
        return [LocalFileResource(file_path) for file_path in self.list_file()]

    def add_resource(self, resource: LocalFileResource | TripleFileResource) -> None:
        if isinstance(resource, TripleFileResource):
            self._add_triple_file_resource(resource)
        elif isinstance(resource, LocalFileResource):
            self._add_local_file_resource(resource)
        else:
            raise ValueError(f"Unknown resource type: {type(resource)}")

    def _add_local_file_resource(self, resource: LocalFileResource):
        import shutil
        from ontobdc.storage.adapter.repository import LoadedStorageGraph
        dataset_path = LoadedStorageGraph.resolve_location_path(self.location)
        target_dir = dataset_path / "payload" / "documents"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / resource.name
        
        shutil.copy2(resource.path, target_file)
        
        # Update dataset.ttl with InternalDocument modeling
        index_file = dataset_path / "dataset.ttl"
        dataset_graph = Graph()
        if index_file.exists():
            dataset_graph.parse(str(index_file), format="turtle")
            
        doc_ref = URIRef(f"{self._dataset}#{resource.name}")
        dataset_graph.add((self._dataset, CT.containsDocument, doc_ref))
        dataset_graph.add((doc_ref, RDF.type, CT.InternalDocument))
        dataset_graph.add((doc_ref, DCTERMS.title, Literal(resource.name)))
        dataset_graph.add((doc_ref, DCTERMS.format, Literal(resource.mimetype)))
        dataset_graph.add((doc_ref, CT.filename, Literal(resource.name)))
        
        dataset_graph.serialize(destination=str(index_file), format="turtle")

    def _add_triple_file_resource(self, resource: TripleFileResource):
        from ontobdc.storage.adapter.repository import LoadedStorageGraph
        dataset_path = LoadedStorageGraph.resolve_location_path(self.location)
        target_dir = dataset_path / "payload" / "triples"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{resource.name}.ttl"

        g = Graph()
        # Fallback parsing format if needed, rdflib tries to guess by extension usually
        try:
            g.parse(str(resource.path))
        except Exception:
            try:
                g.parse(str(resource.path), format="turtle")
            except Exception:
                try:
                    g.parse(str(resource.path), format="xml")
                except Exception:
                    g.parse(str(resource.path), format="json-ld")
        
        g.serialize(destination=str(target_file), format="turtle")

        # Update dataset.ttl with Linkset modeling
        index_file = dataset_path / "dataset.ttl"
        dataset_graph = Graph()

        if index_file.exists():
            dataset_graph.parse(str(index_file), format="turtle")
            
        linkset_ref = URIRef(f"{self._dataset}#{target_file.name}")
        dataset_graph.add((self._dataset, CT.containsLinkset, linkset_ref))
        dataset_graph.add((linkset_ref, RDF.type, CT.Linkset))
        dataset_graph.add((linkset_ref, DCTERMS.title, Literal(target_file.name)))
        dataset_graph.add((linkset_ref, DCTERMS.format, Literal("text/turtle")))
        dataset_graph.add((linkset_ref, CT.filename, Literal(target_file.name)))
        
        dataset_graph.serialize(destination=str(index_file), format="turtle")

    def _load(self, graph: Graph) -> str:
        container_refs: List[URIRef] = list(graph.objects(self._dataset, DCTERMS.isPartOf))
        if len(container_refs) == 0:
            raise ValueError(f"Dataset {self.id} has no container reference")

        title_list: List[Literal] = list(graph.objects(self._dataset, DCTERMS.title))
        if title_list:
            self._data['title'] = {title.language: title.value for title in title_list}

        location_list: List[URIRef] = list(graph.objects(self._dataset, PROV.atLocation))
        if location_list:
            dataset_location: str = str(location_list[0]).strip()
            self._data['location'] = dataset_location

        # Add the dataset to the matching container
        for container_data in list(graph.subjects(RDF.type, CT.ContainerDescription)):
            if str(container_data) == str(container_refs[0]):
                self._data['container'] = str(container_data)
                break
        
        from ontobdc.storage.adapter.repository import LoadedStorageGraph
        return str(LoadedStorageGraph.resolve_location_path(self.location))

