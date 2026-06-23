
import os
from typing import Any, Dict
from datetime import datetime, timezone
from ontobdc.storage.adapter.resource import LocalFileResource
from rdflib import URIRef, Literal, Graph
from ontobdc.storage import get_storage_file
from ontobdc.shared.adapter.config import ConfigDataAdapter
from rdflib.namespace import DCTERMS, RDF, XSD, PROV
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.storage.domain.port.repository import ContainerRepositoryPort, RootContainerRepositoryPort

CT = get_ontology_by_prefix("ct")


class StorageContainerAdapter(ContainerRepositoryPort):
    """
    Adapter for storage containers.
    """
    def __init__(self, graph: LoadedStorageGraph, id: str):
        self._graph: LoadedStorageGraph = graph
        self._id: str = id

    @property
    def id(self) -> str:
        """
        Get the ID of the container.

        :return: The ID of the container.
        """
        return self._id

    @property
    def title(self) -> str:
        """
        Get the title of the container.

        :return: The title of the container.
        """
        return f"Storage Container ({self._id})"

    @property
    def description(self) -> str:
        """
        Get the description of the container.

        :return: The description of the container.
        """
        return f"Storage container for {self._id}"

    def container_exists(self) -> bool:
        """
        Check if the container exists.

        :return: True if the container exists, False otherwise.
        """
        g: Graph = self._graph.graph
        container_type = CT.ContainerDescription
        identifier_pred = DCTERMS.identifier
        for s in g.subjects(RDF.type, container_type):
            for obj in g.objects(s, identifier_pred):
                if str(obj) == self._id:
                    return True

        return False

    def save(self) -> None:
        """
        Save the repository to the storage file.
        """
        if not self.container_exists():
            self._create_container()

        # Save the graph
        self._graph.serialize(destination=get_storage_file(), format='turtle')

    def delete(self, force: bool = False) -> None:
        """
        Delete the container from the graph.

        :param force: Whether to force the deletion, even if the container has datasets.
        """
        # Prevent deleting root container
        if self._id == "urn:ontobdc:storage/local":
            raise ValueError("Cannot delete the root container (urn:ontobdc:storage/local).")

        if self.container_exists():
            self._delete_container()
        else:
            raise ValueError(f"Container {self._id} does not exist.")

    def to_json(self) -> Dict[str, Any]:
        """
        Convert the container to a JSON object.

        :return: A JSON object with the container information.
        """
        return {
            "id": self._id,
            "graph": self._graph.serialize(format='json-ld').decode('utf-8')
        }

    def _create_container(self):
        """
        Create the container with the required types.
        """
        if self._id.startswith("urn:"):
            container_ref = URIRef(self._id)
        else:
            container_ref = URIRef(f"urn:ontobdc:storage/local/{self._id}")
        identifier_pred = DCTERMS.identifier
        description_pred = CT.description
        creation_date_pred = CT.creationDate
        title_pred = DCTERMS.title

        # Get the underlying rdflib Graph from LoadedStorageGraph
        g: Graph = self._graph.graph

        # Check if container exists using our own container_exists method
        if not self.container_exists():
            # Create the container with the required types
            g.add((container_ref, RDF.type, CT.ContainerDescription))
            g.add((container_ref, RDF.type, DCTERMS.Location))

            # Add the required properties
            g.add((container_ref, description_pred, Literal(self.description, lang="en")))
            
            # Create creation date
            creation_date = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            g.add((container_ref, creation_date_pred, Literal(creation_date, datatype=XSD.dateTime)))
            
            g.add((container_ref, title_pred, Literal(self.title, lang="en")))

        # Check if identifier exists
        has_identifier = (container_ref, identifier_pred, Literal(self._id)) in g
        if not has_identifier:
            g.add((container_ref, identifier_pred, Literal(self._id)))

        # Save the graph
        self._graph.serialize(destination=get_storage_file(), format='turtle')

    def _delete_container(self):
        """
        Delete the container from the graph.
        """
        g: Graph = self._graph.graph
        container_ref = URIRef(self._id)
        container_type = CT.ContainerDescription
        identifier_pred = DCTERMS.identifier

        for s in g.subjects(RDF.type, container_type):
            for obj in g.objects(s, identifier_pred):
                if str(obj) == self._id:
                    container_ref = s
                    break
            if container_ref:
                break
        
        if not container_ref:
            raise ValueError(f"Container '{self._id}' not found.")

        # Remove all triples about the container
        g.remove((container_ref, None, None))
        # Also remove any triples that reference the container
        g.remove((None, None, container_ref))

        # Save the graph
        self._graph.serialize(destination=get_storage_file(), format='turtle')


class StorageLocalContainerAdapter(StorageContainerAdapter):
    """
    Adapter for storage local containers.
    """
    def __init__(self, graph: LoadedStorageGraph, id: str, location: str):
        super().__init__(graph, id)
        self._location: str = location

    @property
    def title(self) -> str:
        """
        Get the title of the container.

        :return: The title of the container.
        """
        # Get the last part of the path for a friendly name
        path = self._location
        if path.startswith("file://"):
            path = path[7:]
        folder_name = os.path.basename(path.rstrip(os.path.sep))
        return f"Storage Container: {folder_name}" if folder_name else "Storage Container"

    @property
    def description(self) -> str:
        """
        Get the description of the container.

        :return: The description of the container.
        """
        return f"Local storage container at {self.title}"

    @property
    def location(self) -> str:
        """
        Get the location of the container.

        :return: The location of the container.
        """
        return self._location

    def register_document(self, document: LocalFileResource):
        """
        Register a document as internal to the container.

        :param document: The document to register as an internal.
        """
        pass

    def _create_container(self):
        """
        Create the container with the required types.
        """
        super()._create_container()

        # Add the location property
        g: Graph = self._graph.graph
        g.add((URIRef(self._id), PROV.atLocation, URIRef(self._location)))

        # Save the graph
        self._graph.serialize(destination=get_storage_file(), format='turtle')


class StorageRootContainerAdapter(StorageLocalContainerAdapter, RootContainerRepositoryPort):
    """
    Adapter for storage root containers.
    """
    @property
    def title(self) -> str:
        """
        Get the title of the container.

        :return: The title of the container.
        """
        return "The Main Storage Index"

    @property
    def description(self) -> str:
        """
        Get the description of the container.

        :return: The description of the container.
        """
        return f"Main storage container for project at {self.title}"

    def __init__(self):
        super().__init__(LoadedStorageGraph(get_storage_file()), "urn:ontobdc:storage/local", f"file://{ConfigDataAdapter().root_dir}")

    def container_exists(self) -> bool:
        """
        Check if root container exists using identifier.
        """
        g: Graph = self._graph.graph
        container_type = CT.ContainerDescription
        identifier_pred = DCTERMS.identifier
        for s in g.subjects(RDF.type, container_type):
            for obj in g.objects(s, identifier_pred):
                if str(obj) == self._id:
                    return True
        return False






