from pathlib import Path

from ontobdc.storage.adapter.bootstrap import ONTOBDC_DIRECTORY_NAME
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    _frictionless_compatible_crate_paths,
    _present_managed_paths,
)


def main(
    print_log: callable = None,
    container_path: str = None,
    root_path: str = None,
) -> int:
    """Add datapackage.json resources for RO-Crate files that are
    frictionless-compatible but not yet described.
    """
    del root_path
    if not container_path:
        return 1

    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    expected_paths = _frictionless_compatible_crate_paths(resolved_container_path)
    if expected_paths is None:
        if print_log is not None:
            print_log(
                "ERROR",
                "Hotfix Container Data Package RO-Crate Synced",
                "The container RO-Crate metadata file could not be read.",
            )
        return 1
    if not expected_paths:
        return 0

    datapackage_path = resolved_container_path / ONTOBDC_DIRECTORY_NAME / "datapackage.json"
    synchronizer = ContainerDataPackageSynchronizer()
    try:
        descriptor = (
            synchronizer._load_descriptor(datapackage_path)
            if datapackage_path.is_file()
            else {"name": "ontobdc_container"}
        )
        resources = synchronizer._resource_descriptors(descriptor)
    except (OSError, ValueError) as error:
        if print_log is not None:
            print_log(
                "ERROR",
                "Hotfix Container Data Package RO-Crate Synced",
                f"Could not read the Data Package descriptor: {error}",
            )
        return 1

    present_paths = _present_managed_paths(resolved_container_path, datapackage_path) or set()
    missing_paths = sorted(expected_paths - present_paths)
    for relative_path in missing_paths:
        resources.append(
            synchronizer._build_local_descriptor(
                relative_path=relative_path,
                container_path=resolved_container_path,
                datapackage_path=datapackage_path,
                existing_descriptor=None,
            )
        )

    descriptor["resources"] = resources
    synchronizer._write_descriptor(datapackage_path, descriptor)
    return 0
