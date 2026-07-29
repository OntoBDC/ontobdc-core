from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import get_container_storage_file_path

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
CT = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")

def _resolve_container_path(container_path: Optional[str]) -> Optional[Path]:
    if not isinstance(container_path, str) or not container_path.strip():
        return None

    return Path(container_path).expanduser().resolve()


def _resolve_root_path(root_path: Optional[str]) -> Optional[Path]:
    if not isinstance(root_path, str) or not root_path.strip():
        return None

    return Path(root_path).expanduser().resolve()


def _build_expected_container_id(container_path: Path, root_path: Path) -> Optional[str]:
    try:
        relative_container_path: Path = container_path.relative_to(root_path)
    except ValueError:
        return None

    encoded_relative_path: str = quote(relative_container_path.as_posix(), safe="/")
    return f"urn:ontobdc:storage/local/{encoded_relative_path}"


def _load_container_graph(container_storage_file_path: Path) -> Optional[Graph]:
    container_graph: Graph = Graph()
    try:
        container_graph.parse(str(container_storage_file_path), format="turtle")
    except Exception:
        return None

    return container_graph


def _resolve_container_subject(container_graph: Graph) -> Optional[URIRef]:
    container_subjects: List[URIRef] = [
        subject
        for subject in container_graph.subjects(RDF.type, OBDC.DataContainer)
        if isinstance(subject, URIRef)
    ]
    if len(container_subjects) != 1:
        return None

    return container_subjects[0]


def _has_required_value(container_graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
    values: List[str] = [
        str(obj).strip()
        for obj in container_graph.objects(subject, predicate)
        if str(obj).strip()
    ]
    return len(values) > 0


def _has_valid_location(container_graph: Graph, subject: URIRef, container_path: Path) -> bool:
    location_values: List[str] = [
        str(location).strip()
        for location in container_graph.objects(subject, PROV.atLocation)
        if str(location).strip()
    ]
    return container_path.as_uri() in location_values


def _has_valid_identifier(
    container_graph: Graph,
    subject: URIRef,
    expected_container_id: str,
) -> bool:
    identifier_values: List[str] = [
        str(identifier).strip()
        for identifier in container_graph.objects(subject, DCTERMS.identifier)
        if str(identifier).strip()
    ]
    return expected_container_id in identifier_values


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_container_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_root_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if not resolved_container_path.is_dir():
        return 1

    expected_container_id: Optional[str] = _build_expected_container_id(
        resolved_container_path,
        resolved_root_path,
    )
    if expected_container_id is None:
        return 1

    container_storage_file_path: Path = get_container_storage_file_path(resolved_container_path)
    if not container_storage_file_path.is_file():
        return 1

    container_graph: Optional[Graph] = _load_container_graph(container_storage_file_path)
    if container_graph is None:
        return 1

    container_subject: Optional[URIRef] = _resolve_container_subject(container_graph)
    if container_subject is None:
        return 1

    if not _has_valid_identifier(container_graph, container_subject, expected_container_id):
        return 1

    if not _has_required_value(container_graph, container_subject, DCTERMS.title):
        return 1

    if not _has_required_value(container_graph, container_subject, CT.description):
        return 1

    if not _has_required_value(container_graph, container_subject, CT.creationDate):
        return 1

    if not _has_valid_location(container_graph, container_subject, resolved_container_path):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
