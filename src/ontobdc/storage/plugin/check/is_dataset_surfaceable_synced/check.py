from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    get_dataset_storage_file_path,
    get_ontobdc_directory,
)

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")

LINKSET_DIRECTORY_NAME: str = "linkset"
TYPE_FILE_NAME: str = "type.ttl"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _load_graph(file_path: Path) -> Optional[Graph]:
    graph: Graph = Graph()
    try:
        graph.parse(str(file_path), format="turtle")
    except Exception:
        return None

    return graph


def _resolve_dataset_subject(dataset_graph: Graph) -> Optional[URIRef]:
    subjects: List[URIRef] = [
        subject
        for subject in dataset_graph.subjects(RDF.type, OBDC.EntityDataset)
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        return None

    return subjects[0]


def _resolve_entity_type(dataset_graph: Graph, dataset_subject: URIRef) -> Optional[URIRef]:
    entity_subjects: List[URIRef] = [
        value
        for value in dataset_graph.objects(dataset_subject, OBDC.hasDataEntity)
        if isinstance(value, URIRef)
    ]
    if len(entity_subjects) != 1:
        return None

    types: List[URIRef] = [
        value
        for value in dataset_graph.objects(entity_subjects[0], RDF.type)
        if isinstance(value, URIRef) and value != OBDC.DataEntity
    ]
    if len(types) != 1:
        return None

    return types[0]


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 when dataset.ttl's obdc:SurfaceableEntity marker for the
    dataset's entity type matches what the locally materialized
    linkset/type.ttl says it should be, 1 when it's stale (the type
    ontology says surfaceable but dataset.ttl doesn't have the marker
    yet). Returns 0 (nothing to check) when linkset/type.ttl was never
    materialized (created before this check existed, or the entity's
    facade had no sibling type.ttl) or the type ontology doesn't mark the
    class at all — there is nothing to sync in either case.
    """
    del root_path

    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    type_ontology_path: Path = (
        get_ontobdc_directory(resolved_dataset_path)
        / LINKSET_DIRECTORY_NAME
        / TYPE_FILE_NAME
    )
    if not type_ontology_path.is_file():
        return 0

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

    type_graph: Optional[Graph] = _load_graph(type_ontology_path)
    if type_graph is None:
        return 1

    should_be_surfaceable: bool = (
        entity_type,
        RDF.type,
        OBDC.SurfaceableEntity,
    ) in type_graph
    if not should_be_surfaceable:
        return 0

    is_marked: bool = (
        entity_type,
        RDF.type,
        OBDC.SurfaceableEntity,
    ) in dataset_graph
    return 0 if is_marked else 1


if __name__ == "__main__":
    raise SystemExit(main())
