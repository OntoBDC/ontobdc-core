import os
import sys
from pathlib import Path
from typing import List, Optional
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, PROV
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import LoadedStorageGraphPort


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None) -> None:
        if print_log:
            print_log("ERROR", "Check Dataset Health", message)
        else:
            print(message, file=sys.stderr)

    try:
        root_storage_file: str = get_storage_file()
        if not os.path.isfile(root_storage_file):
            _print_error_log(f"Root storage file not found: {root_storage_file}", print_log)
            return 1

        root_graph: LoadedStorageGraphPort = LoadedStorageGraph(root_storage_file)

        for _, container_config_dir, container_storage_file in root_graph.containers:
            if not os.path.isfile(container_storage_file):
                _print_error_log(f"Container storage file not found: {container_storage_file}", print_log)
                return 1

            container_graph: Graph = Graph()
            container_graph.parse(container_storage_file, format="turtle")
            dataset_refs: List[URIRef] = _dataset_refs(container_graph)

            for dataset_ref in dataset_refs:
                container_ref: Optional[URIRef] = _first_uri_ref(
                    container_graph.objects(dataset_ref, DCTERMS.isPartOf)
                )
                if not isinstance(container_ref, URIRef):
                    _print_error_log(
                        f"Dataset '{dataset_ref}' has no valid container reference in '{container_storage_file}'.",
                        print_log,
                    )
                    return 1

                container_ref_value: str = str(container_ref).strip()
                if _is_malformed_local_reference(container_ref_value):
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' has malformed container reference "
                            f"'{container_ref_value}' in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

                location_ref: Optional[URIRef] = _first_uri_ref(
                    container_graph.objects(dataset_ref, PROV.atLocation)
                )
                if not isinstance(location_ref, URIRef):
                    _print_error_log(
                        f"Dataset '{dataset_ref}' has no valid location in '{container_storage_file}'.",
                        print_log,
                    )
                    return 1

                location_value: str = str(location_ref).strip()
                if _is_malformed_local_reference(location_value):
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' has malformed location "
                            f"'{location_value}' in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

                resolved_location: Path = LoadedStorageGraph.resolve_location_path(location_value)
                if not resolved_location.exists():
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' points to a missing directory "
                            f"'{resolved_location}' in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

                if not resolved_location.is_dir():
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' points to a non-directory path "
                            f"'{resolved_location}' in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

                if resolved_location.parent.name == ".__ontobdc__" or container_config_dir in str(resolved_location):
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' points inside the config directory "
                            f"'{resolved_location}' in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

                dataset_index_file: Path = resolved_location / "index.ttl"
                if not dataset_index_file.is_file():
                    _print_error_log(
                        (
                            f"Dataset '{dataset_ref}' is missing '{dataset_index_file}' "
                            f"in '{container_storage_file}'."
                        ),
                        print_log,
                    )
                    return 1

        return 0
    except Exception as error:
        _print_error_log(f"Error checking dataset health: {error}", print_log)
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

    if len(dataset_refs) > 0:
        return dataset_refs

    for dataset_ref in graph.objects(None, DCTERMS.hasPart):
        if not isinstance(dataset_ref, URIRef):
            continue
        if dataset_ref in seen_dataset_refs:
            continue
        seen_dataset_refs.add(dataset_ref)
        dataset_refs.append(dataset_ref)

    return dataset_refs


def _first_uri_ref(values: object) -> Optional[URIRef]:
    for value in values:
        if isinstance(value, URIRef):
            return value

    return None


def _is_malformed_local_reference(value: str) -> bool:
    normalized_value: str = value.strip()
    return "/.__ontobdc__/urn:ontobdc:storage/local/" in normalized_value or "/.__ontobdc__/" in normalized_value


if __name__ == "__main__":
    sys.exit(main())
