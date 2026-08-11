from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

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

FACADE_FILE_NAME: str = "facade.ttl"
LINKSET_DIRECTORY_NAME: str = "linkset"


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


def _resolve_entity_subject(
    dataset_graph: Graph,
    dataset_subject: URIRef,
) -> Optional[URIRef]:
    values: List[URIRef] = [
        value
        for value in dataset_graph.objects(dataset_subject, OBDC.hasDataEntity)
        if isinstance(value, URIRef)
    ]
    if len(values) != 1:
        return None

    return values[0]


def _resolve_entity_type(
    dataset_graph: Graph,
    entity_subject: URIRef,
) -> Optional[URIRef]:
    types: List[URIRef] = [
        value
        for value in dataset_graph.objects(entity_subject, RDF.type)
        if isinstance(value, URIRef) and value != OBDC.DataEntity
    ]
    if len(types) != 1:
        return None

    return types[0]


def _resolve_facade_uri(
    dataset_graph: Graph,
    entity_subject: URIRef,
) -> Optional[URIRef]:
    values: List[URIRef] = [
        value
        for value in dataset_graph.objects(entity_subject, DCTERMS.conformsTo)
        if isinstance(value, URIRef)
    ]
    if len(values) != 1:
        return None

    return values[0]


def _local_name(predicate: URIRef) -> str:
    predicate_value: str = str(predicate).strip()
    if "#" in predicate_value:
        return predicate_value.rsplit("#", 1)[-1].strip()
    return predicate_value.rstrip("/").rsplit("/", 1)[-1].strip()


def _facade_describes(
    facade_graph: Graph,
    entity_type: URIRef,
    facade_uri: URIRef,
) -> bool:
    """The facade file (own ontology namespace, not obdc:) must link the
    entity's rdf:type to the facade concept via *hasDataEntityFacade*, and
    the facade concept must expose at least one *hasFacadeField* — matching
    the structure ContainerEntityInstanceRepository reads for LIST.
    """
    is_linked: bool = any(
        _local_name(predicate) == "hasDataEntityFacade"
        for _, predicate, _ in facade_graph.triples((entity_type, None, facade_uri))
    )
    if not is_linked:
        return False

    return any(
        _local_name(predicate) == "hasFacadeField"
        for _, predicate, _ in facade_graph.triples((facade_uri, None, None))
    )


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 when the dataset's single DataEntity conforms to a facade
    that linkset/facade.ttl actually describes with at least one field, 1
    otherwise. There is no hotfix for this check: the source facade file is
    only known to the context/entity-facade resolution layer, which the
    storage layer must not depend on.
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

    entity_subject: Optional[URIRef] = _resolve_entity_subject(
        dataset_graph, dataset_subject
    )
    if entity_subject is None:
        return 1

    entity_type: Optional[URIRef] = _resolve_entity_type(
        dataset_graph, entity_subject
    )
    if entity_type is None:
        return 1

    facade_uri: Optional[URIRef] = _resolve_facade_uri(
        dataset_graph, entity_subject
    )
    if facade_uri is None:
        return 1

    facade_path: Path = (
        get_ontobdc_directory(resolved_dataset_path)
        / LINKSET_DIRECTORY_NAME
        / FACADE_FILE_NAME
    )
    if not facade_path.is_file():
        return 1

    facade_graph: Optional[Graph] = _load_graph(facade_path)
    if facade_graph is None:
        return 1

    if not _facade_describes(facade_graph, entity_type, facade_uri):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
