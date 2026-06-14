
import os
import sys
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageContainerCrate, LoadedStorageGraph
from ontobdc.storage.domain.port.repository import LoadedStorageContainerCratePort, LoadedStorageGraphPort


CRATE_METADATA_FILE = "ro-crate-metadata.json"


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check RO-Crate", message)

    try:
        root_storage_file = get_storage_file()
        if not os.path.exists(root_storage_file):
            _print_error_log("Root storage file not found.", print_log)
            return 1

        root_graph: LoadedStorageGraphPort = LoadedStorageGraph(root_storage_file)

        for _, container_config_dir, _ in root_graph.containers:
            crate_metadata: LoadedStorageContainerCratePort = LoadedStorageContainerCrate(os.path.join(container_config_dir, CRATE_METADATA_FILE))

            if not crate_metadata.is_valid():
                _print_error_log(
                    f"Invalid or missing RO-Crate metadata: {crate_metadata.file_path}",
                    print_log,
                )
                return 1

        return 0
    except Exception as error:
        _print_error_log(f"Error checking RO-Crate health: {error}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
