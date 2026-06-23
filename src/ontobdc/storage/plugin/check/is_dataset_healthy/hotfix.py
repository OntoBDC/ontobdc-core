
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, PROV
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.storage import STORAGE_URN_PREFIX, get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph

DATASET_URN_PREFIX: str = f"{STORAGE_URN_PREFIX}dataset/"


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None) -> None:
        if print_log:
            print_log("INFO", "Hotfix Dataset Health", message)

    def _print_error_log(message: str, print_log: callable = None) -> None:
        if print_log:
            print_log("ERROR", "Hotfix Dataset Health", message)
        else:
            print(message, file=sys.stderr)

    try:
        root_storage_file: str = get_storage_file()
        if not os.path.isfile(root_storage_file):
            _print_error_log(f"Root storage file not found: {root_storage_file}", print_log)
            return 1

        root_graph: LoadedStorageGraph = LoadedStorageGraph(root_storage_file)

        for container_subject, container_config_dir, container_storage_file in root_graph.containers:
            if not os.path.isfile(container_storage_file):
                continue

            container_graph: Graph = Graph()
            container_graph.parse(container_storage_file, format="turtle")

            dataset_refs: List[URIRef] = _dataset_refs(container_graph)
            if len(dataset_refs) == 0:
                continue

            container_id: Optional[str] = _container_id(root_graph.graph, container_subject)
            if not isinstance(container_id, str) or not container_id.strip():
                raise ValueError(f"Container identifier not found for '{container_subject}'.")

            canonical_container_ref: URIRef = URIRef(container_id.strip())
            container_path: Path = Path(container_config_dir).parent.resolve()
            touched: bool = False

            for dataset_ref in dataset_refs:
                current_location_ref: Optional[URIRef] = _first_uri_ref(
                    container_graph.objects(dataset_ref, PROV.atLocation)
                )
                current_location_value: Optional[str] = (
                    str(current_location_ref).strip() if isinstance(current_location_ref, URIRef) else None
                )

                normalized_dataset_path: Path = _normalize_dataset_path(
                    dataset_ref=dataset_ref,
                    container_path=container_path,
                    current_location=current_location_value,
                )
                normalized_dataset_uri: URIRef = URIRef(normalized_dataset_path.as_uri())

                current_container_ref: Optional[URIRef] = _first_uri_ref(
                    container_graph.objects(dataset_ref, DCTERMS.isPartOf)
                )

                # 1. Fix isPartOf container reference
                if current_container_ref != canonical_container_ref:
                    container_graph.remove((dataset_ref, DCTERMS.isPartOf, None))
                    container_graph.add((dataset_ref, DCTERMS.isPartOf, canonical_container_ref))
                    touched = True

                # Fix hasPart (inverse relation)
                has_part_refs: List[URIRef] = list(container_graph.subjects(DCTERMS.hasPart, dataset_ref))
                if has_part_refs != [canonical_container_ref]:
                    container_graph.remove((None, DCTERMS.hasPart, dataset_ref))
                    container_graph.add((canonical_container_ref, DCTERMS.hasPart, dataset_ref))
                    touched = True

                # 2. Fix atLocation reference and directory
                if current_location_ref != normalized_dataset_uri:
                    container_graph.remove((dataset_ref, PROV.atLocation, None))
                    container_graph.add((dataset_ref, PROV.atLocation, normalized_dataset_uri))
                    touched = True

                # Create physical directory if missing
                if not normalized_dataset_path.exists():
                    normalized_dataset_path.mkdir(parents=True, exist_ok=True)
                    touched = True
                    _print_info_log(f"Created dataset directory '{normalized_dataset_path}'.", print_log)

                # 3. Ensure index.ttl file exists in the directory
                index_file_path: Path = normalized_dataset_path / "index.ttl"
                if not index_file_path.is_file():
                    _write_empty_dataset_index(index_file_path)
                    touched = True
                    _print_info_log(f"Created empty dataset index at '{index_file_path}'.", print_log)

                if touched:
                    _print_info_log(
                        (
                            f"Normalized dataset '{dataset_ref}' in '{container_storage_file}' "
                            f"to '{normalized_dataset_path}'."
                        ),
                        print_log,
                    )

            if touched:
                container_graph.serialize(destination=container_storage_file, format="turtle")

        return 0
    except Exception as error:
        _print_error_log(f"Error applying dataset hotfix: {error}", print_log)
        return 1


def _dataset_refs(graph: Graph) -> List[URIRef]:
    dataset_refs: List[URIRef] = []
    seen_dataset_refs: set[URIRef] = set()

    for dataset_ref in graph.subjects(DCTERMS.isPartOf, None):
        if not isinstance(dataset_ref, URIRef):
            continue
        if dataset_ref in seen_dataset_refs:
            continue
        seen_dataset_refs.add(dataset_ref)
        dataset_refs.append(dataset_ref)

    for dataset_ref in graph.objects(None, DCTERMS.hasPart):
        if not isinstance(dataset_ref, URIRef):
            continue
        if dataset_ref in seen_dataset_refs:
            continue
        seen_dataset_refs.add(dataset_ref)
        dataset_refs.append(dataset_ref)

    return dataset_refs


def _first_uri_ref(values: Iterable[object]) -> Optional[URIRef]:
    for value in values:
        if isinstance(value, URIRef):
            return value

    return None


def _container_id(graph: Graph, container_subject: URIRef) -> Optional[str]:
    for identifier in graph.objects(container_subject, DCTERMS.identifier):
        if isinstance(identifier, Literal):
            normalized_identifier: str = str(identifier).strip()
            if normalized_identifier:
                return normalized_identifier

    return None


def _normalize_dataset_path(
    dataset_ref: URIRef,
    container_path: Path,
    current_location: Optional[str],
) -> Path:
    candidate_paths: List[Path] = []

    if isinstance(current_location, str) and current_location.strip():
        candidate_paths.extend(_location_candidates(current_location))

    dataset_relative_path: Optional[str] = _dataset_relative_path(dataset_ref)
    if isinstance(dataset_relative_path, str) and dataset_relative_path.strip():
        candidate_paths.append((container_path / dataset_relative_path).resolve())

    deduplicated_candidates: List[Path] = []
    seen_candidates: set[str] = set()
    for candidate_path in candidate_paths:
        candidate_key: str = str(candidate_path)
        if candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        deduplicated_candidates.append(candidate_path)

    for candidate_path in deduplicated_candidates:
        if candidate_path.exists() and candidate_path.is_dir():
            return candidate_path.resolve()

    if len(deduplicated_candidates) > 0:
        return deduplicated_candidates[0]

    raise ValueError(
        (
            f"Dataset '{dataset_ref}' could not be normalized. "
            f"Tried: {[str(candidate) for candidate in deduplicated_candidates]}"
        )
    )


def _location_candidates(location_value: str) -> List[Path]:
    candidate_paths: List[Path] = []
    normalized_location: str = location_value.strip()

    candidate_paths.append(LoadedStorageGraph.resolve_location_path(normalized_location).resolve())

    root_dir: Optional[str] = ConfigDataAdapter().root_dir
    if isinstance(root_dir, str) and root_dir.strip():
        if "urn:ontobdc:storage/local/" in normalized_location:
            root_relative_path: str = normalized_location.split("urn:ontobdc:storage/local/", 1)[1]
            candidate_paths.append((Path(root_dir) / root_relative_path).resolve())

        parsed_location = urlparse(normalized_location)
        parsed_path: str = parsed_location.path if parsed_location.scheme else normalized_location
        broken_root_marker: str = f"{os.sep}urn:ontobdc:storage/local{os.sep}"
        if broken_root_marker in parsed_path:
            root_relative_path = parsed_path.split(broken_root_marker, 1)[1]
            candidate_paths.append((Path(root_dir) / root_relative_path).resolve())

    return candidate_paths


def _dataset_relative_path(dataset_ref: URIRef) -> Optional[str]:
    normalized_ref: str = str(dataset_ref).strip()
    if normalized_ref.startswith(DATASET_URN_PREFIX):
        return normalized_ref[len(DATASET_URN_PREFIX):].strip("/")

    return Path(normalized_ref).name.strip() or None


def _write_empty_dataset_index(index_file_path: Path) -> None:
    index_file_path.parent.mkdir(parents=True, exist_ok=True)
    Graph().serialize(destination=str(index_file_path), format="turtle")


if __name__ == "__main__":
    sys.exit(main())
