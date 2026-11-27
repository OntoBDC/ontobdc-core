from pathlib import Path
from typing import Any, Dict, List, Optional

from brasidatacenter.tool.adapter.entity_info import entity_info_in_graph
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.repository import LoadedStorageGraph


class DatasetOntologies:
    """
    The ontologies the datasets of a container keep in their own ``ontology/resource``: where an addon puts the ontology
    of the entity it makes, so that the entity is described with its data. What they say about an entity is read the
    same way as what the ontologies BrasidataCenter ships say.
    """

    @classmethod
    def containers(cls, current: Optional[Path]) -> List[Path]:
        """
        The containers whose datasets are searched: the one a command runs in, when it runs in one, and every container
        the storage registers. What a dataset keeps of an entity is the same wherever the command runs, and the root
        a command runs in is not always the container that has the dataset.
        """
        found: List[Path] = [] if current is None else [current.expanduser().resolve()]
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(StorageFileLocator.resolve())
        container_config_dir: str
        for _, container_config_dir, _ in storage_graph.containers:
            container: Path = Path(container_config_dir).expanduser().parent.resolve()
            if container not in found:
                found.append(container)

        return found

    @classmethod
    def files(cls, container_paths: List[Path]) -> List[Path]:
        """Each ontology file kept in a registered dataset of the containers."""
        files: List[Path] = []
        container_path: Path
        for container_path in container_paths:
            dataset_path: Path
            for dataset_path in RegisteredDatasets.of(container_path):
                resource: Path = dataset_path / EntityFacadeLocator.DATASET_ONTOLOGY
                files.extend(sorted(resource.glob("*.ttl")) if resource.is_dir() else [])

        return files

    @classmethod
    def graphs(cls, container_paths: List[Path]) -> List[Graph]:
        """One graph for each ontology file kept in a registered dataset of the containers."""
        graphs: List[Graph] = []
        file: Path
        for file in cls.files(container_paths):
            graph: Graph = Graph()
            graph.parse(str(file), format="turtle")
            graphs.append(graph)

        return graphs

    @classmethod
    def entity_iri(cls, container_paths: List[Path], name: str) -> Optional[str]:
        """
        The IRI of the entity type the name stands for, ignoring case: the one whose facade a dataset of the container
        keeps and whose local name is the name. None when no dataset keeps one.
        """
        found: List[str] = []
        graph: Graph
        for graph in cls.graphs(container_paths):
            facade: Any
            for facade in graph.subjects(RDF.type, EntityFacadeLocator.FACADE.DataEntityFacade):
                entity: Any
                for entity in graph.objects(facade, EntityFacadeLocator.FACADE.isFacadeOf):
                    local: str = str(entity).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                    if isinstance(entity, URIRef) and local.casefold() == name.casefold() and str(entity) not in found:
                        found.append(str(entity))

        if len(found) > 1:
            raise ValueError(f"More than one entity of the datasets of the containers is named {name}: {', '.join(found)}.")

        return found[0] if found else None

    @classmethod
    def facade_info(cls, container_paths: List[Path], entity_iri: str) -> Optional[Dict[str, Any]]:
        """What the facade a dataset of the container keeps says of the entity, none when no dataset keeps one."""
        graph: Graph
        for graph in cls.graphs(container_paths):
            information: Optional[Dict[str, Any]] = entity_info_in_graph(graph, entity_iri)
            if information is not None:
                return information

        return None
