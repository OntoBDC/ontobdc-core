from pathlib import Path
from typing import Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    ensure_ontobdc_directory,
    get_container_storage_file_path,
    get_storage_file_path,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
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


def _get_single_object(container_graph: Graph, subject: URIRef, predicate: URIRef) -> Optional[object]:
    values: List[object] = list(container_graph.objects(subject, predicate))
    if len(values) != 1:
        return None

    value: object = values[0]
    if isinstance(value, Literal):
        if not str(value).strip():
            return None
    if isinstance(value, URIRef):
        if not str(value).strip():
            return None

    return value


def _extract_required_triples(container_graph: Graph, subject: URIRef) -> Optional[Dict[URIRef, object]]:
    identifier_obj: Optional[object] = _get_single_object(container_graph, subject, DCTERMS.identifier)
    title_obj: Optional[object] = _get_single_object(container_graph, subject, DCTERMS.title)
    created_obj: Optional[object] = _get_single_object(container_graph, subject, CT.creationDate)
    description_obj: Optional[object] = _get_single_object(container_graph, subject, CT.description)
    location_obj: Optional[object] = _get_single_object(container_graph, subject, PROV.atLocation)

    if not isinstance(identifier_obj, Literal):
        return None
    if not isinstance(title_obj, Literal):
        return None
    if not isinstance(created_obj, Literal):
        return None
    if not isinstance(description_obj, Literal):
        return None
    if not isinstance(location_obj, URIRef):
        return None

    return {
        DCTERMS.identifier: identifier_obj,
        DCTERMS.title: title_obj,
        CT.creationDate: created_obj,
        CT.description: description_obj,
        PROV.atLocation: location_obj,
    }


def _bind_namespaces(graph: Graph) -> None:
    graph.bind("dcterms", DCTERMS)
    graph.bind("ct", CT)
    graph.bind("prov", PROV)
    graph.bind("xsd", XSD)
    graph.bind("obdc", OBDC)


def _remove_subject_triples(graph: Graph, subject: URIRef) -> None:
    for predicate, obj in list(graph.predicate_objects(subject)):
        graph.remove((subject, predicate, obj))


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if check_container_metadata_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    container_storage_file_path: Path = get_container_storage_file_path(resolved_container_path)
    storage_file_path: Path = get_storage_file_path(resolved_root_path)
    if not container_storage_file_path.is_file():
        return 1

    container_graph: Optional[Graph] = _load_graph(container_storage_file_path)
    if storage_file_path.is_file():
        storage_graph: Optional[Graph] = _load_graph(storage_file_path)
    else:
        storage_graph = Graph()

    if container_graph is None or storage_graph is None:
        return 1

    container_subject: Optional[URIRef] = _resolve_single_container_subject(container_graph)
    if container_subject is None:
        return 1

    expected_triples: Optional[Dict[URIRef, object]] = _extract_required_triples(container_graph, container_subject)
    if expected_triples is None:
        return 1

    identifier_value: object = expected_triples.get(DCTERMS.identifier)
    if not isinstance(identifier_value, Literal):
        return 1
    identifier_obj: Literal = identifier_value

    ensure_ontobdc_directory(resolved_root_path)

    for subject in list(storage_graph.subjects(DCTERMS.identifier, identifier_obj)):
        if isinstance(subject, URIRef):
            _remove_subject_triples(storage_graph, subject)

    _bind_namespaces(storage_graph)

    storage_graph.add((container_subject, RDF.type, OBDC.DataContainer))
    for predicate, obj in expected_triples.items():
        storage_graph.add((container_subject, predicate, obj))

    serialized_graph: bytes = storage_graph.serialize(format="turtle", encoding="utf-8")
    storage_file_path.write_bytes(serialized_graph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
