from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.storage.adapter.bootstrap import (
    get_dataset_storage_file_path,
    get_ontobdc_directory,
)
from ontobdc.storage.plugin.check.is_dataset_surfaceable_synced.check import (
    OBDC,
    TYPE_FILE_NAME,
    LINKSET_DIRECTORY_NAME,
    _load_graph,
    _resolve_dataset_subject,
    _resolve_entity_type,
    _resolve_path,
)


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Add the missing obdc:SurfaceableEntity marker to dataset.ttl for the
    dataset's entity type, using the locally materialized
    linkset/type.ttl as the source of truth. Returns 0 on success (or when
    there was nothing to fix), 1 when it can't be resolved.
    """
    del root_path

    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    dataset_storage_file_path: Path = get_dataset_storage_file_path(
        resolved_dataset_path
    )
    dataset_graph: Optional[Graph] = _load_graph(dataset_storage_file_path)
    if dataset_graph is None:
        return 1

    dataset_subject: Optional[URIRef] = _resolve_dataset_subject(dataset_graph)
    if dataset_subject is None:
        return 1

    entity_type: Optional[URIRef] = _resolve_entity_type(
        dataset_graph, dataset_subject
    )
    if entity_type is None:
        return 0

    type_ontology_path: Path = (
        get_ontobdc_directory(resolved_dataset_path)
        / LINKSET_DIRECTORY_NAME
        / TYPE_FILE_NAME
    )
    if not type_ontology_path.is_file():
        return 0

    type_graph: Optional[Graph] = _load_graph(type_ontology_path)
    if type_graph is None:
        return 1

    if (entity_type, RDF.type, OBDC.SurfaceableEntity) not in type_graph:
        return 0

    if (entity_type, RDF.type, OBDC.SurfaceableEntity) in dataset_graph:
        return 0

    dataset_graph.add((entity_type, RDF.type, OBDC.SurfaceableEntity))
    try:
        dataset_graph.serialize(
            destination=str(dataset_storage_file_path), format="turtle"
        )
    except Exception:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
