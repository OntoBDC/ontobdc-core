
import os
import sys
import warnings
from rocrate.rocrate import ROCrate
from ontobdc.storage import get_storage_file, CRATE_METADATA_FILE
from ontobdc.storage.adapter.repository import LoadedStorageContainerCrate, LoadedStorageGraph
from ontobdc.storage.domain.port.repository import LoadedStorageContainerCratePort, LoadedStorageGraphPort


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix RO-Crate", message)

    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix RO-Crate", message)

    try:
        root_storage_file = get_storage_file()
        if not os.path.exists(root_storage_file):
            _print_error_log("Root storage file not found.", print_log)
            return 1

        root_graph: LoadedStorageGraphPort = LoadedStorageGraph(root_storage_file)

        for _, container_config_dir, container_storage_file in root_graph.containers:
            if container_storage_file == root_storage_file:
                continue

            container_ro_crate_file: str = os.path.join(container_config_dir, CRATE_METADATA_FILE)
            if not os.path.exists(container_ro_crate_file) or not os.path.isfile(container_ro_crate_file):
                container_ro_crate: ROCrate = ROCrate(gen_preview=False)

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=r"No source for .*")
                    container_ro_crate.write(container_config_dir)
                    _print_info_log(f"Created RO-Crate file {container_ro_crate_file}", print_log)

            container_ro_crate: LoadedStorageContainerCratePort = LoadedStorageContainerCrate(container_ro_crate_file)
            container_ro_crate.refresh()
            _print_info_log(f"The RO-Crate file {container_ro_crate_file} is up to date.", print_log)


        return 0
    except Exception as e:
        _print_error_log(f"Error checking containers: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
