from typing import Dict, Optional

from ontobdc.storage.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_datapackage_frictionless_valid,
)
from ontobdc.storage.plugin.check.is_container_datapackage_updated.check import (
    main as check_datapackage_updated,
)
from ontobdc.storage.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)
from ontobdc.storage.plugin.check.is_dataset_facade_valid.check import (
    main as check_dataset_facade_valid,
)
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.storage.plugin.check.is_dataset_surfaceable_synced.check import (
    main as check_dataset_surfaceable_synced,
)

# The two datapackage checks are the generic container-level ones, reused
# unmodified: they only take a directory ("container_path" is just the
# parameter name) and a dataset directory is a valid target — its own
# .__ontobdc__/datapackage.json, synced against its own payload/ files.


def evaluate(dataset_path: str, root_path: str) -> Dict[str, int]:
    """Per-check results (0 = healthy) — DatasetHealthyCapability reports these."""
    return {
        "dataset_metadata_ready": check_dataset_metadata_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ),
        "dataset_container_index_ready": check_dataset_container_index_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ),
        "dataset_datapackage_updated": check_datapackage_updated(
            container_path=dataset_path,
            root_path=root_path,
        ),
        "dataset_datapackage_frictionless_valid": check_datapackage_frictionless_valid(
            container_path=dataset_path,
            root_path=root_path,
        ),
        "dataset_facade_valid": check_dataset_facade_valid(
            dataset_path=dataset_path,
            root_path=root_path,
        ),
        "dataset_surfaceable_synced": check_dataset_surfaceable_synced(
            dataset_path=dataset_path,
            root_path=root_path,
        ),
    }


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 only when every sub-check passes, 1 otherwise."""
    if not dataset_path or not root_path:
        return 1

    results: Dict[str, int] = evaluate(dataset_path, root_path)
    return 0 if all(value == 0 for value in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
