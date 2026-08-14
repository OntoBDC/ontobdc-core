from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.adapter.bootstrap import get_dataset_storage_file_path

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
CT = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


def _resolve_dataset_path(dataset_path: Optional[str]) -> Optional[Path]:
    if not isinstance(dataset_path, str) or not dataset_path.strip():
        return None

    return Path(dataset_path).expanduser().resolve()


def _resolve_root_path(root_path: Optional[str]) -> Optional[Path]:
    if not isinstance(root_path, str) or not root_path.strip():
        return None

    return Path(root_path).expanduser().resolve()


def _build_expected_dataset_id(dataset_path: Path, root_path: Path) -> Optional[str]:
    try:
        relative_dataset_path: Path = dataset_path.relative_to(root_path)
    except ValueError:
        return None

    encoded_relative_path: str = quote(relative_dataset_path.as_posix(), safe="/")
    return f"urn:ontobdc:storage/dataset/{encoded_relative_path}"


def _load_dataset_graph(dataset_storage_file_path: Path) -> Optional[Graph]:
    dataset_graph: Graph = Graph()
    try:
        dataset_graph.parse(str(dataset_storage_file_path), format="turtle")
    except Exception:
        return None

    return dataset_graph


def _resolve_dataset_subject(dataset_graph: Graph) -> Optional[URIRef]:
    dataset_subjects: List[URIRef] = [
        subject
        for subject in dataset_graph.subjects(RDF.type, OBDC.EntityDataset)
        if isinstance(subject, URIRef)
    ]
    if len(dataset_subjects) != 1:
        return None

    return dataset_subjects[0]


def _has_valid_ontology_subject(dataset_graph: Graph, dataset_storage_file_path: Path) -> bool:
    ontology_ref: URIRef = URIRef(dataset_storage_file_path.as_uri())
    return (ontology_ref, RDF.type, OWL.Ontology) in dataset_graph


def _has_required_value(dataset_graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
    values: List[str] = [
        str(obj).strip()
        for obj in dataset_graph.objects(subject, predicate)
        if str(obj).strip()
    ]
    return len(values) > 0


def _has_valid_location(dataset_graph: Graph, subject: URIRef, dataset_path: Path) -> bool:
    location_values: List[str] = [
        str(location).strip()
        for location in dataset_graph.objects(subject, PROV.atLocation)
        if str(location).strip()
    ]
    return dataset_path.as_uri() in location_values


def _resolve_expected_container_id(dataset_path: Path, root_path: Path) -> Optional[str]:
    container_path: Path = dataset_path.parent.resolve()

    try:
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file(str(root_path)))
    except Exception:
        return None

    for container in storage_graph.storage_graph.list_containers():
        if not isinstance(container, dict):
            continue

        container_id = container.get("id")
        container_location = container.get("location")
        if not isinstance(container_id, str) or not container_id.strip():
            continue
        if not isinstance(container_location, str) or not container_location.strip():
            continue

        if Path(container_location).expanduser().resolve() == container_path:
            return container_id.strip()

    return None


def _has_valid_container_reference(
    dataset_graph: Graph,
    subject: URIRef,
    expected_container_id: str,
) -> bool:
    container_refs: List[str] = [
        str(container_ref).strip()
        for container_ref in dataset_graph.objects(subject, OBDC.belongsToDataContainer)
        if str(container_ref).strip()
    ]
    return expected_container_id in container_refs


def _has_data_entity(dataset_graph: Graph, subject: URIRef) -> bool:
    data_entity_values: List[str] = [
        str(data_entity).strip()
        for data_entity in dataset_graph.objects(subject, OBDC.hasDataEntity)
        if str(data_entity).strip()
    ]
    return len(data_entity_values) > 0


def _has_valid_identifier(
    dataset_graph: Graph,
    subject: URIRef,
    expected_dataset_id: str,
) -> bool:
    identifier_values: List[str] = [
        str(identifier).strip()
        for identifier in dataset_graph.objects(subject, DCTERMS.identifier)
        if str(identifier).strip()
    ]
    return expected_dataset_id in identifier_values


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_dataset_path: Optional[Path] = _resolve_dataset_path(dataset_path)
    resolved_root_path: Optional[Path] = _resolve_root_path(root_path)
    if resolved_dataset_path is None or resolved_root_path is None:
        return 1

    if not resolved_dataset_path.is_dir():
        return 1

    expected_dataset_id: Optional[str] = _build_expected_dataset_id(
        resolved_dataset_path,
        resolved_root_path,
    )
    if expected_dataset_id is None:
        return 1

    expected_container_id: Optional[str] = _resolve_expected_container_id(
        resolved_dataset_path,
        resolved_root_path,
    )
    if expected_container_id is None:
        return 1

    dataset_storage_file_path: Path = get_dataset_storage_file_path(resolved_dataset_path)
    if not dataset_storage_file_path.is_file():
        return 1

    dataset_graph: Optional[Graph] = _load_dataset_graph(dataset_storage_file_path)
    if dataset_graph is None:
        return 1

    if not _has_valid_ontology_subject(dataset_graph, dataset_storage_file_path):
        return 1

    dataset_subject: Optional[URIRef] = _resolve_dataset_subject(dataset_graph)
    if dataset_subject is None:
        return 1

    if not _has_valid_identifier(dataset_graph, dataset_subject, expected_dataset_id):
        return 1

    if not _has_required_value(dataset_graph, dataset_subject, DCTERMS.title):
        return 1

    if not _has_required_value(dataset_graph, dataset_subject, DCTERMS.description):
        return 1

    if not _has_required_value(dataset_graph, dataset_subject, CT.creationDate):
        return 1

    if not _has_valid_container_reference(
        dataset_graph,
        dataset_subject,
        expected_container_id,
    ):
        return 1

    if not _has_data_entity(dataset_graph, dataset_subject):
        return 1

    if not _has_valid_location(dataset_graph, dataset_subject, resolved_dataset_path):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
