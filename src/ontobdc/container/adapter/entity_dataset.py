from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef

from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.container.plugin.check.is_dataset_surfaceable_synced.check import (
    _resolve_dataset_subject,
    _resolve_entity_type,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class EntityDatasets:
    """
    The datasets of a container that hold a given entity type.
    """

    @classmethod
    def of(cls, container_path: Path, entity_iri: str) -> List[Path]:
        """
        Every registered dataset of the container whose data entity is of the
        type ``entity_iri``, in the order the container lists them.
        """
        matching: List[Path] = []
        dataset_path: Path
        for dataset_path in RegisteredDatasets.of(container_path):
            if cls._entity_type(dataset_path) == entity_iri:
                matching.append(dataset_path)

        return matching

    @classmethod
    def first(cls, container_path: Path, entity_iri: str) -> Optional[Path]:
        datasets: List[Path] = cls.of(container_path, entity_iri)
        return datasets[0] if datasets else None

    @staticmethod
    def _entity_type(dataset_path: Path) -> Optional[str]:
        metadata_path: Path = StorageBootstrap.get_dataset_storage_file_path(dataset_path)
        if not metadata_path.is_file():
            return None

        graph: Graph = Graph()
        graph.parse(str(metadata_path), format="turtle")
        subject: Optional[URIRef] = _resolve_dataset_subject(graph)
        if subject is None:
            return None

        entity_type: Optional[URIRef] = _resolve_entity_type(graph, subject)
        return str(entity_type) if entity_type is not None else None
