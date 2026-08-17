import json
from pathlib import Path
from typing import Optional, Set

from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageLayoutConstants,
)
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
    FrictionlessFormatRegistry,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.check import (
    _extract_has_part_ids,
)


def _frictionless_compatible_crate_paths(container_path: Path) -> Optional[Set[str]]:
    """RO-Crate `hasPart` file ids, filtered to frictionless-compatible formats.

    Returns None when the crate can't be read at all (distinguished from an
    empty-but-readable crate, which is a legitimate `set()`).
    """
    crate_path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)
    if not crate_path.is_file():
        return None

    try:
        crate_data = json.loads(crate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if not isinstance(crate_data, dict):
        return None

    file_ids = _extract_has_part_ids(crate_data)
    if file_ids is None:
        return None

    return {
        file_id
        for file_id in file_ids
        if FrictionlessFormatRegistry.supports(
            file_id.rsplit(".", 1)[-1].lower()
        )
    }


def _present_managed_paths(container_path: Path, datapackage_path: Path) -> Optional[Set[str]]:
    if not datapackage_path.is_file():
        return set()

    synchronizer = ContainerDataPackageSynchronizer()
    try:
        descriptor = synchronizer._load_descriptor(datapackage_path)
        resources = synchronizer._resource_descriptors(descriptor)
    except (OSError, ValueError):
        return None

    present: Set[str] = set()
    for resource in resources:
        managed_path = synchronizer._managed_container_path(
            resource_descriptor=resource,
            datapackage_path=datapackage_path,
            container_path=container_path,
        )
        if managed_path is not None:
            present.add(managed_path)

    return present


def main(container_path: str = None, root_path: str = None) -> int:
    """Return 0 when every frictionless-compatible RO-Crate file is a
    datapackage.json resource, 1 when at least one is missing, and 2 when
    the container/crate/descriptor can't be read.
    """
    del root_path
    if not container_path:
        return 2

    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    if not resolved_container_path.is_dir():
        return 2

    expected_paths = _frictionless_compatible_crate_paths(resolved_container_path)
    if expected_paths is None:
        return 2
    if not expected_paths:
        return 0

    datapackage_path = resolved_container_path / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME / "datapackage.json"
    present_paths = _present_managed_paths(resolved_container_path, datapackage_path)
    if present_paths is None:
        return 2

    return 0 if expected_paths.issubset(present_paths) else 1
