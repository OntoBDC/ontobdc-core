from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ontobdc.storage.adapter.bootstrap import StorageLayoutConstants
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
)


def evaluate(container_path: str) -> int:
    """
    Return 0 when synchronized, 1 when absent or stale, and 2 when invalid.
    """
    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    if not resolved_container_path.is_dir():
        return 2

    datapackage_path: Path = (
        resolved_container_path / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME / "datapackage.json"
    )
    if not datapackage_path.is_file():
        return 1

    synchronizer = ContainerDataPackageSynchronizer()
    try:
        descriptor: Dict[str, Any] = synchronizer._load_descriptor(
            datapackage_path
        )
        original_resources: List[Dict[str, Any]] = (
            synchronizer._resource_descriptors(descriptor)
        )
        resource_paths: List[str] = ContainerDataPackageSynchronizer.list_resource_paths(
            resolved_container_path
        )
        inventory: Set[str] = set(resource_paths)

        existing_by_path: Dict[str, Dict[str, Any]] = {}
        external_resources: List[Dict[str, Any]] = []

        for resource_descriptor in original_resources:
            managed_path: Optional[str] = synchronizer._managed_container_path(
                resource_descriptor=resource_descriptor,
                datapackage_path=datapackage_path,
                container_path=resolved_container_path,
            )
            if managed_path is None:
                external_resources.append(dict(resource_descriptor))
                continue

            if managed_path not in inventory or managed_path in existing_by_path:
                continue

            existing_by_path[managed_path] = dict(resource_descriptor)

        synchronized_resources: List[Dict[str, Any]] = []
        for relative_path in resource_paths:
            synchronized_resources.append(
                synchronizer._build_local_descriptor(
                    relative_path=relative_path,
                    container_path=resolved_container_path,
                    datapackage_path=datapackage_path,
                    existing_descriptor=existing_by_path.get(relative_path),
                )
            )

        synchronized_resources.extend(external_resources)
        expected_descriptor: Dict[str, Any] = dict(descriptor)
        expected_descriptor.setdefault("name", "ontobdc_container")
        expected_descriptor["resources"] = synchronized_resources
    except (OSError, ValueError):
        return 2

    return 0 if descriptor == expected_descriptor else 1


def main(
    print_log: callable = None,
    container_path: str = None,
    root_path: str = None,
) -> int:
    del root_path
    if not container_path:
        return 2

    result: int = evaluate(container_path)
    if print_log is not None and result != 0:
        if result == 2:
            print_log(
                "ERROR",
                "Check Container Data Package Updated",
                "The container Data Package descriptor is invalid.",
            )
        else:
            print_log(
                "WARNING",
                "Check Container Data Package Updated",
                "The container Data Package descriptor is absent or stale.",
            )
    return result
