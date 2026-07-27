from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    ensure_ontobdc_directory,
    get_container_storage_file_path,
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


def _build_container_id(container_path: Path, root_path: Path) -> Optional[str]:
    try:
        relative_container_path: Path = container_path.relative_to(root_path)
    except ValueError:
        return None

    return f"urn:ontobdc:storage/local/{relative_container_path.as_posix()}"


def _build_container_title(container_path: Path) -> str:
    container_name: str = container_path.name.strip()
    if container_name:
        return f"Storage Container: {container_name}"

    return "Storage Container"


def _build_container_graph(
    container_id: str,
    container_path: Path,
) -> Graph:
    container_graph: Graph = Graph()
    container_graph.bind("dcterms", DCTERMS)
    container_graph.bind("ct", CT)
    container_graph.bind("prov", PROV)
    container_graph.bind("xsd", XSD)
    container_graph.bind("obdc", OBDC)

    container_ref: URIRef = URIRef(container_id)
    created_at: Literal = Literal(
        datetime.now(timezone.utc).isoformat(),
        datatype=XSD.dateTime,
    )
    container_title: str = _build_container_title(container_path)
    container_description: str = f"Local storage container at {container_title}"

    container_graph.add((container_ref, RDF.type, OBDC.DataContainer))
    container_graph.add((container_ref, DCTERMS.identifier, Literal(container_id)))
    container_graph.add((container_ref, DCTERMS.title, Literal(container_title, lang="en")))
    container_graph.add((container_ref, CT.description, Literal(container_description, lang="en")))
    container_graph.add((container_ref, CT.creationDate, created_at))
    container_graph.add((container_ref, PROV.atLocation, URIRef(container_path.as_uri())))

    return container_graph


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    container_id: Optional[str] = _build_container_id(resolved_container_path, resolved_root_path)
    if container_id is None:
        return 1

    try:
        resolved_container_path.mkdir(parents=True, exist_ok=True)
        ensure_ontobdc_directory(resolved_container_path)

        container_storage_file_path: Path = get_container_storage_file_path(resolved_container_path)
        container_graph: Graph = _build_container_graph(container_id, resolved_container_path)
        serialized_graph: bytes = container_graph.serialize(format="turtle", encoding="utf-8")
        container_storage_file_path.write_bytes(serialized_graph)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
