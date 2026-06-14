import os
import sys
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from rdflib import Graph
from ontobdc.storage import EMPTY_STORAGE_GRAPH, get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph


def main(print_log: callable = None) -> int:

    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Storage", message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Storage", "Failed to hotfix storage: " + message)

    try:
        root_storage_file: str = get_storage_file()
        if not os.path.exists(root_storage_file):
            _print_error_log("Root storage file not found.", print_log)
            return 1

        root_graph: LoadedStorageGraph = LoadedStorageGraph(root_storage_file)

        for s, container_config_dir, container_storage_file in root_graph.containers:
            if container_storage_file == root_storage_file:
                continue

            # Create config dir if not exists
            if not os.path.exists(container_config_dir):
                os.makedirs(container_config_dir, exist_ok=True)
                _print_info_log(f"Created {container_config_dir}", print_log)
                
            # Create storage file if not exists
            if not os.path.exists(container_storage_file):
                with open(container_storage_file, "w", encoding="utf-8") as f:
                    f.write(EMPTY_STORAGE_GRAPH)
                _print_info_log(f"Created {container_storage_file}", print_log)

            g_container: Graph = Graph()
            g_container.parse(container_storage_file, format="turtle")
            g_container.bind("ct", get_ontology_by_prefix("ct"))

            # Update container data:
            # 1. Remove ONLY the properties that are defined in the root graph for this container
            for p, o in root_graph.graph.predicate_objects(s):
                # Remove any existing values for this predicate in the local container
                g_container.remove((s, p, None))

            # 2. Add the correct properties from the root graph
            for p, o in root_graph.graph.predicate_objects(s):
                g_container.add((s, p, o))

            g_container.serialize(destination=container_storage_file, format="turtle")
            _print_info_log(f"Synced data for container in {container_storage_file}", print_log)
            
        return 0
    except Exception as e:
        _print_error_log(f"Error applying hotfix: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
