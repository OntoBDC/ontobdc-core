
import os
import sys
from rdflib import URIRef
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.storage.domain.port.repository import LoadedStorageGraphPort


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Container Config", message)

    try:
        root_storage_file: str = get_storage_file()
        if not os.path.isfile(root_storage_file):
            _print_error_log(f"Root storage file not found: {root_storage_file}", print_log)
            return 1

        root_graph: LoadedStorageGraphPort = LoadedStorageGraph(root_storage_file)

        for container, container_config_dir, container_file in root_graph.containers:
            if not isinstance(container, URIRef):
                _print_error_log(f"Container {container} is not a URIRef.", print_log)
                return 1

            if not os.path.isdir(container_config_dir):
                _print_error_log(f"Container config directory not found: {container_config_dir}", print_log)
                return 1

            if not os.path.isfile(container_file):
                _print_error_log(f"Container file not found: {container_file}", print_log)
                return 1

        if not root_graph.is_valid():
            _print_error_log("One or more container configuration files are invalid or empty.", print_log)
            return 1

        return 0
    except Exception as e:
        _print_error_log(f"Error checking containers: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
