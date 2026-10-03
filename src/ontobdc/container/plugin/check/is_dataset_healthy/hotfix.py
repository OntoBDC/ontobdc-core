from typing import Callable, Optional, Tuple

from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_datapackage_frictionless_valid,
)
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.hotfix import (
    main as hotfix_datapackage_frictionless_valid,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.check import (
    main as check_datapackage_updated,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.hotfix import (
    main as hotfix_datapackage_updated,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.hotfix import (
    main as hotfix_dataset_container_index_ready,
)
from ontobdc.container.plugin.check.is_dataset_facade_valid.check import (
    main as check_dataset_facade_valid,
)
from ontobdc.container.plugin.check.is_dataset_facade_valid.hotfix import (
    main as hotfix_dataset_facade_valid,
)
from ontobdc.container.plugin.check.is_dataset_healthy.check import (
    main as check_dataset_healthy,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.hotfix import (
    main as hotfix_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_structure_valid.check import (
    main as check_dataset_structure_valid,
)
from ontobdc.container.plugin.check.is_dataset_structure_valid.hotfix import (
    main as hotfix_dataset_structure_valid,
)
from ontobdc.container.plugin.check.is_dataset_surfaceable_synced.check import (
    main as check_dataset_surfaceable_synced,
)
from ontobdc.container.plugin.check.is_dataset_surfaceable_synced.hotfix import (
    main as hotfix_dataset_surfaceable_synced,
)

DatasetStep = Callable[[str, str], int]

# Every repairable part of a dataset's health, as (check, hotfix), in the
# order one depends on the other: the structure before what is written in
# it, the metadata before the container index entry that mirrors it, and
# the Data Package last, once every payload file is in place. The Data
# Package checks are the container-level ones: a dataset directory is a
# valid target for them.
REPAIRS: Tuple[Tuple[DatasetStep, DatasetStep], ...] = (
    (
        lambda dataset, root: check_dataset_structure_valid(dataset_path=dataset, root_path=root),
        lambda dataset, root: hotfix_dataset_structure_valid(dataset_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_dataset_metadata_ready(dataset_path=dataset, root_path=root),
        lambda dataset, root: hotfix_dataset_metadata_ready(dataset_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_dataset_container_index_ready(dataset_path=dataset, root_path=root),
        lambda dataset, root: hotfix_dataset_container_index_ready(dataset_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_dataset_facade_valid(dataset_path=dataset, root_path=root),
        lambda dataset, root: hotfix_dataset_facade_valid(dataset_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_dataset_surfaceable_synced(dataset_path=dataset, root_path=root),
        lambda dataset, root: hotfix_dataset_surfaceable_synced(dataset_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_datapackage_updated(container_path=dataset, root_path=root),
        lambda dataset, root: hotfix_datapackage_updated(container_path=dataset, root_path=root),
    ),
    (
        lambda dataset, root: check_datapackage_frictionless_valid(container_path=dataset, root_path=root),
        lambda dataset, root: hotfix_datapackage_frictionless_valid(container_path=dataset, root_path=root),
    ),
)


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Repair every failing part of the dataset's health, in dependency
    order, and return the resulting health: 0 only when every check of
    ``is_dataset_healthy`` passes."""
    if not dataset_path or not root_path:
        return 1

    check: DatasetStep
    hotfix: DatasetStep
    for check, hotfix in REPAIRS:
        if check(dataset_path, root_path) != 0:
            hotfix(dataset_path, root_path)

    return check_dataset_healthy(dataset_path=dataset_path, root_path=root_path)


if __name__ == "__main__":
    raise SystemExit(main())
