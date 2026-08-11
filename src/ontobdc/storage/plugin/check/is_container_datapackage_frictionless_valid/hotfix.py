from pathlib import Path

from ontobdc.storage.adapter.bootstrap import ONTOBDC_DIRECTORY_NAME
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.plugin.check.is_container_datapackage_frictionless_valid.check import (
    FRICTIONLESS_COMPATIBLE_FORMATS,
)


def main(
    print_log: callable = None,
    container_path: str = None,
    root_path: str = None,
) -> int:
    """Remove local datapackage.json resources whose format isn't frictionless-compatible.

    External resources (paths outside the container) are left untouched —
    this only prunes entries the container itself owns and describes.
    """
    del root_path
    if not container_path:
        return 1

    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    datapackage_path = resolved_container_path / ONTOBDC_DIRECTORY_NAME / "datapackage.json"
    if not datapackage_path.is_file():
        return 0  # nothing to prune

    synchronizer = ContainerDataPackageSynchronizer()
    try:
        descriptor = synchronizer._load_descriptor(datapackage_path)
        resources = synchronizer._resource_descriptors(descriptor)
    except (OSError, ValueError) as error:
        if print_log is not None:
            print_log(
                "ERROR",
                "Hotfix Container Data Package Frictionless Valid",
                f"Could not read the Data Package descriptor: {error}",
            )
        return 1

    kept = []
    for resource in resources:
        managed_path = synchronizer._managed_container_path(
            resource_descriptor=resource,
            datapackage_path=datapackage_path,
            container_path=resolved_container_path,
        )
        if managed_path is None:
            kept.append(resource)  # external resources are out of scope
            continue

        resource_format = str(resource.get("format", "")).strip().lower()
        if resource_format in FRICTIONLESS_COMPATIBLE_FORMATS:
            kept.append(resource)

    descriptor["resources"] = kept
    synchronizer._write_descriptor(datapackage_path, descriptor)
    return 0
