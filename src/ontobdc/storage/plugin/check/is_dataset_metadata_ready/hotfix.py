import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, XSD

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.adapter.bootstrap import (
    ensure_ontobdc_directory,
    get_dataset_storage_file_path,
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


def _build_dataset_id(dataset_path: Path, root_path: Path) -> Optional[str]:
    try:
        relative_dataset_path: Path = dataset_path.relative_to(root_path)
    except ValueError:
        return None

    return f"urn:ontobdc:storage/dataset/{relative_dataset_path.as_posix()}"


def _build_dataset_title(dataset_path: Path) -> str:
    dataset_name: str = dataset_path.name.strip()
    if dataset_name:
        return f"Storage Dataset: {dataset_name}"

    return "Storage Dataset"


def _build_data_entity_id(dataset_id: str) -> str:
    dataset_hash: str = hashlib.sha256(dataset_id.encode("utf-8")).hexdigest()
    return f"{dataset_id}/{dataset_hash}"


def _resolve_parent_container(dataset_path: Path, root_path: Path) -> Optional[Tuple[str, Path]]:
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
            return container_id.strip(), container_path

    return None


def _build_dataset_graph(
    dataset_id: str,
    dataset_path: Path,
    dataset_storage_file_path: Path,
    container_id: str,
) -> Graph:
    dataset_graph: Graph = Graph()
    dataset_graph.bind("dcterms", DCTERMS)
    dataset_graph.bind("ct", CT)
    dataset_graph.bind("prov", PROV)
    dataset_graph.bind("xsd", XSD)
    dataset_graph.bind("obdc", OBDC)
    dataset_graph.bind("owl", OWL)

    dataset_ref: URIRef = URIRef(dataset_id)
    dataset_metadata_ref: URIRef = URIRef(dataset_storage_file_path.as_uri())
    container_ref: URIRef = URIRef(container_id)
    data_entity_ref: URIRef = URIRef(_build_data_entity_id(dataset_id))
    created_at: Literal = Literal(
        datetime.now().replace(microsecond=0).isoformat(),
        datatype=XSD.dateTime,
    )
    dataset_title: str = _build_dataset_title(dataset_path)
    dataset_description: str = f"Storage dataset located at {dataset_path.as_uri()}"

    dataset_graph.add((dataset_metadata_ref, RDF.type, OWL.Ontology))
    dataset_graph.add((dataset_ref, RDF.type, OBDC.EntityDataset))
    dataset_graph.add((dataset_ref, OBDC.belongsToDataContainer, container_ref))
    dataset_graph.add((dataset_ref, OBDC.hasDataEntity, data_entity_ref))
    dataset_graph.add((dataset_ref, DCTERMS.identifier, Literal(dataset_id)))
    dataset_graph.add((dataset_ref, DCTERMS.title, Literal(dataset_title)))
    dataset_graph.add((dataset_ref, DCTERMS.description, Literal(dataset_description)))
    dataset_graph.add((dataset_ref, CT.creationDate, created_at))
    dataset_graph.add((dataset_ref, PROV.atLocation, URIRef(dataset_path.as_uri())))

    return dataset_graph


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_dataset_path is None or resolved_root_path is None:
        return 1

    dataset_id: Optional[str] = _build_dataset_id(resolved_dataset_path, resolved_root_path)
    if dataset_id is None:
        return 1

    parent_container: Optional[Tuple[str, Path]] = _resolve_parent_container(
        resolved_dataset_path,
        resolved_root_path,
    )
    if parent_container is None:
        return 1

    try:
        resolved_dataset_path.mkdir(parents=True, exist_ok=True)
        ensure_ontobdc_directory(resolved_dataset_path)

        dataset_storage_file_path: Path = get_dataset_storage_file_path(resolved_dataset_path)
        dataset_graph: Graph = _build_dataset_graph(
            dataset_id,
            resolved_dataset_path,
            dataset_storage_file_path,
            parent_container[0],
        )
        serialized_graph: bytes = dataset_graph.serialize(format="turtle", encoding="utf-8")
        dataset_storage_file_path.write_bytes(serialized_graph)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
