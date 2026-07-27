from pathlib import Path
from typing import Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    get_container_storage_file_path,
    get_dataset_storage_file_path,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
CT = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


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


def _resolve_single_container_subject(container_graph: Graph) -> Optional[URIRef]:
    subjects: List[URIRef] = [
        subject
        for subject in container_graph.subjects(RDF.type, OBDC.DataContainer)
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        return None

    return subjects[0]


def _resolve_single_dataset_subject(dataset_graph: Graph) -> Optional[URIRef]:
    subjects: List[URIRef] = [
        subject
        for subject in dataset_graph.subjects(RDF.type, OBDC.EntityDataset)
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        return None

    return subjects[0]


def _get_single_object(dataset_graph: Graph, subject: URIRef, predicate: URIRef) -> Optional[object]:
    values: List[object] = list(dataset_graph.objects(subject, predicate))
    if len(values) != 1:
        return None

    value: object = values[0]
    if isinstance(value, Literal) and not str(value).strip():
        return None
    if isinstance(value, URIRef) and not str(value).strip():
        return None

    return value


def _extract_required_dataset_triples(
    dataset_graph: Graph,
    dataset_subject: URIRef,
    container_subject: URIRef,
) -> Optional[Dict[URIRef, object]]:
    title_obj: Optional[object] = _get_single_object(dataset_graph, dataset_subject, DCTERMS.title)
    description_obj: Optional[object] = _get_single_object(dataset_graph, dataset_subject, DCTERMS.description)
    location_obj: Optional[object] = _get_single_object(dataset_graph, dataset_subject, PROV.atLocation)
    if not isinstance(title_obj, Literal):
        return None
    if not isinstance(description_obj, Literal):
        return None
    if not isinstance(location_obj, URIRef):
        return None

    return {
        DCTERMS.title: title_obj,
        DCTERMS.description: description_obj,
        PROV.atLocation: location_obj,
        OBDC.belongsToDataContainer: container_subject,
    }


def _has_only_expected_dataset_triples(
    container_graph: Graph,
    dataset_subject: URIRef,
    expected_triples: Dict[URIRef, object],
) -> bool:
    allowed_predicates: List[URIRef] = [RDF.type] + list(expected_triples.keys())

    found_types: List[object] = list(container_graph.objects(dataset_subject, RDF.type))
    if found_types != [OBDC.EntityDataset]:
        return False

    for predicate, expected_obj in expected_triples.items():
        actual_values: List[object] = list(container_graph.objects(dataset_subject, predicate))
        if actual_values != [expected_obj]:
            return False

    for predicate, obj in container_graph.predicate_objects(dataset_subject):
        if predicate not in allowed_predicates:
            return False
        if predicate == RDF.type and obj != OBDC.EntityDataset:
            return False

    return True


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_dataset_path is None or resolved_root_path is None:
        return 1

    if check_dataset_metadata_ready(
        dataset_path=str(resolved_dataset_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    resolved_container_path: Path = resolved_dataset_path.parent.resolve()
    if check_container_metadata_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    dataset_storage_file_path: Path = get_dataset_storage_file_path(resolved_dataset_path)
    if not dataset_storage_file_path.is_file():
        return 1

    container_storage_file_path: Path = get_container_storage_file_path(resolved_container_path)
    if not container_storage_file_path.is_file():
        return 1

    dataset_graph: Optional[Graph] = _load_graph(dataset_storage_file_path)
    container_graph: Optional[Graph] = _load_graph(container_storage_file_path)
    if dataset_graph is None or container_graph is None:
        return 1

    dataset_subject: Optional[URIRef] = _resolve_single_dataset_subject(dataset_graph)
    if dataset_subject is None:
        return 1

    container_subject: Optional[URIRef] = _resolve_single_container_subject(container_graph)
    if container_subject is None:
        return 1

    expected_container_subject: Optional[object] = _get_single_object(
        dataset_graph,
        dataset_subject,
        OBDC.belongsToDataContainer,
    )
    if expected_container_subject != container_subject:
        return 1

    expected_triples: Optional[Dict[URIRef, object]] = _extract_required_dataset_triples(
        dataset_graph=dataset_graph,
        dataset_subject=dataset_subject,
        container_subject=container_subject,
    )
    if expected_triples is None:
        return 1

    if (container_subject, OBDC.hasEntityDataset, dataset_subject) not in container_graph:
        return 1

    if not _has_only_expected_dataset_triples(
        container_graph,
        dataset_subject,
        expected_triples,
    ):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
