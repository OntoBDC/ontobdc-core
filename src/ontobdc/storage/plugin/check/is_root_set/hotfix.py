
import os
import sys
from ontobdc.storage import get_storage_file, EMPTY_STORAGE_GRAPH
from ontobdc.storage.adapter.container import StorageRootContainerAdapter


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Root Container", message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Root Container", "Failed to hotfix root container: " + message)

    try:
        storage_path: str = get_storage_file()

        if not os.path.exists(storage_path):
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            with open(storage_path, "w", encoding="utf-8") as f:
                f.write(EMPTY_STORAGE_GRAPH)
            _print_info_log(f"Created storage file at {storage_path}", print_log)

        root_container: StorageRootContainerAdapter = StorageRootContainerAdapter()
        if not root_container.container_exists():
            root_container.save()
            _print_info_log("Created root container in storage file.", print_log)

        return 0
    except Exception as e:
        _print_error_log(f"Error applying hotfix: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
