from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageLayoutConstants,
)
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
    FrictionlessFormatRegistry,
)


def _incompatible_resources(container_path: Path) -> Optional[List[Dict[str, Any]]]:
    """Local (container-managed) resources whose format isn't in the allowlist.

    Returns None when the descriptor can't be read at all (check should
    report "invalid" rather than "has incompatible resources").
    """
    datapackage_path = container_path / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME / "datapackage.json"
    if not datapackage_path.is_file():
        return []  # nothing to prune yet — container_datapackage_updated runs first

    synchronizer = ContainerDataPackageSynchronizer()
    try:
        descriptor = synchronizer._load_descriptor(datapackage_path)
        resources = synchronizer._resource_descriptors(descriptor)
    except (OSError, ValueError):
        return None

    incompatible: List[Dict[str, Any]] = []
    for resource in resources:
        managed_path = synchronizer._managed_container_path(
            resource_descriptor=resource,
            datapackage_path=datapackage_path,
            container_path=container_path,
        )
        if managed_path is None:
            continue  # external resources are out of scope for this check

        resource_format = str(resource.get("format", "")).strip().lower()
        if not FrictionlessFormatRegistry.supports(resource_format):
            incompatible.append(resource)

    return incompatible


def main(container_path: str = None, root_path: str = None) -> int:
    """Return 0 when every local resource is frictionless-compatible, 1 when
    at least one isn't, and 2 when the container/descriptor can't be read.
    """
    del root_path
    if not container_path:
        return 2

    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    if not resolved_container_path.is_dir():
        return 2

    incompatible = _incompatible_resources(resolved_container_path)
    if incompatible is None:
        return 2

    return 0 if not incompatible else 1
