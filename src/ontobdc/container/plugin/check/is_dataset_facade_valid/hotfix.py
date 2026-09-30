from pathlib import Path
from shutil import copyfile
from typing import Optional

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.container.plugin.check.is_dataset_facade_valid.check import (
    FACADE_FILE_NAME,
    LINKSET_DIRECTORY_NAME,
    PAYLOAD_DIRECTORY_NAME,
    _resolve_path,
    main as check_dataset_facade_valid,
)

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Materialize the canonical facade when absent, without overwriting."""
    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    facade_path: Path = (
        resolved_dataset_path
        / PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / FACADE_FILE_NAME
    )
    if facade_path.exists():
        return check_dataset_facade_valid(
            dataset_path=dataset_path,
            root_path=root_path,
        )

    try:
        source_path: Path = Path(
            _ontology_adapter.get_ontology_path(
                prefix="obdc_view",
                type="facade",
            )
        )
        facade_path.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source_path, facade_path)
    except (FileNotFoundError, OSError, ValueError):
        return 1

    return check_dataset_facade_valid(
        dataset_path=dataset_path,
        root_path=root_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
