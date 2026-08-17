from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.bootstrap import (
    ensure_ontobdc_directory,
    get_container_storage_file_path,
)
from ontobdc.storage.adapter.identifier import (
    generate_container_id,
    is_valid_container_id,
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


def _is_contained(container_path: Path, root_path: Path) -> bool:
    try:
        container_path.relative_to(root_path)
        return True
    except ValueError:
        return False


def _existing_container_id(
    container_storage_file_path: Path,
) -> Optional[str]:
    """The container's existing, already-valid identifier, if any.

    Identity is minted once and kept for the container's lifetime — this
    never recomputes an id from the path, it only recovers one already on
    disk so a healthy container is left untouched.
    """
    existing = _load_existing_container_graph(container_storage_file_path)
    if existing is None:
        return None

    container_graph, container_subject = existing
    identifier: Optional[object] = container_graph.value(
        container_subject, DCTERMS.identifier
    )
    candidate: str = str(identifier or "").strip()
    if candidate and is_valid_container_id(candidate):
        return candidate

    return None


def _build_container_title(container_path: Path) -> str:
    container_name: str = container_path.name.strip()
    if container_name:
        return f"Storage Container: {container_name}"

    return "Storage Container"


def _bind_namespaces(container_graph: Graph) -> None:
    container_graph.bind("dcterms", DCTERMS)
    container_graph.bind("ct", CT)
    container_graph.bind("prov", PROV)
    container_graph.bind("xsd", XSD)
    container_graph.bind("obdc", OBDC)


def _load_existing_container_graph(
    container_storage_file_path: Path,
) -> Optional[Tuple[Graph, URIRef]]:
    if not container_storage_file_path.is_file():
        return None

    container_graph: Graph = Graph()
    try:
        container_graph.parse(
            str(container_storage_file_path),
            format="turtle",
        )
    except Exception:
        return None

    container_subjects = [
        subject
        for subject in container_graph.subjects(
            RDF.type,
            OBDC.DataContainer,
        )
        if isinstance(subject, URIRef)
    ]
    if len(container_subjects) != 1:
        return None

    return container_graph, container_subjects[0]


def _rewrite_container_subject(
    source_graph: Graph,
    source_subject: URIRef,
    target_subject: URIRef,
) -> Graph:
    rewritten_graph: Graph = Graph()
    for prefix, namespace in source_graph.namespaces():
        rewritten_graph.bind(prefix, namespace)
    _bind_namespaces(rewritten_graph)

    for subject, predicate, object_value in source_graph:
        rewritten_graph.add(
            (
                target_subject if subject == source_subject else subject,
                predicate,
                target_subject if object_value == source_subject else object_value,
            )
        )

    return rewritten_graph


def _ensure_semantic_metadata(
    container_graph: Graph,
    container_ref: URIRef,
    container_path: Path,
) -> None:
    container_title: str = _build_container_title(container_path)
    if not any(container_graph.objects(container_ref, DCTERMS.title)):
        container_graph.add(
            (
                container_ref,
                DCTERMS.title,
                Literal(container_title, lang="en"),
            )
        )

    if not any(container_graph.objects(container_ref, CT.description)):
        container_graph.add(
            (
                container_ref,
                CT.description,
                Literal(
                    f"Local storage container at {container_title}",
                    lang="en",
                ),
            )
        )

    if not any(container_graph.objects(container_ref, CT.creationDate)):
        container_graph.add(
            (
                container_ref,
                CT.creationDate,
                Literal(
                    datetime.now(timezone.utc).isoformat(),
                    datatype=XSD.dateTime,
                ),
            )
        )


def _build_container_graph(
    container_id: str,
    container_path: Path,
    container_storage_file_path: Path,
) -> Graph:
    container_ref: URIRef = URIRef(container_id)
    existing = _load_existing_container_graph(container_storage_file_path)

    if existing is None:
        container_graph: Graph = Graph()
        _bind_namespaces(container_graph)
    else:
        source_graph, source_subject = existing
        container_graph = _rewrite_container_subject(
            source_graph,
            source_subject,
            container_ref,
        )

    container_graph.add((container_ref, RDF.type, OBDC.DataContainer))
    container_graph.remove((container_ref, DCTERMS.identifier, None))
    container_graph.add(
        (container_ref, DCTERMS.identifier, Literal(container_id))
    )
    container_graph.remove((container_ref, PROV.atLocation, None))
    container_graph.add(
        (
            container_ref,
            PROV.atLocation,
            URIRef(container_path.as_uri()),
        )
    )
    _ensure_semantic_metadata(
        container_graph,
        container_ref,
        container_path,
    )
    return container_graph


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if not _is_contained(resolved_container_path, resolved_root_path):
        return 1

    try:
        resolved_container_path.mkdir(parents=True, exist_ok=True)
        ensure_ontobdc_directory(resolved_container_path)

        container_storage_file_path: Path = get_container_storage_file_path(
            resolved_container_path
        )
        container_id: str = (
            _existing_container_id(container_storage_file_path)
            or generate_container_id()
        )
        container_graph: Graph = _build_container_graph(
            container_id,
            resolved_container_path,
            container_storage_file_path,
        )
        serialized_graph: bytes = container_graph.serialize(
            format="turtle",
            encoding="utf-8",
        )
        container_storage_file_path.write_bytes(serialized_graph)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
