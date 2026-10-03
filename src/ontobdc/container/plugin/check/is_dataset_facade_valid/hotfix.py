from pathlib import Path
from shutil import copyfile
from typing import Optional

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary
from ontobdc.container.plugin.check.is_dataset_facade_valid.check import (
    FACADE_FILE_NAME,
    FACADE_SHAPES_IRI,
    LINKSET_DIRECTORY_NAME,
    PAYLOAD_DIRECTORY_NAME,
    _resolve_path,
    main as check_dataset_facade_valid,
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

    source_path: Path = BrasidataCenterOntologyLibrary().path(FACADE_SHAPES_IRI)
    try:
        facade_path.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source_path, facade_path)
    except OSError:
        return 1

    return check_dataset_facade_valid(
        dataset_path=dataset_path,
        root_path=root_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
