from pathlib import Path
from typing import Optional, Tuple

ONTOBDC_DIRECTORY_NAME: str = ".__ontobdc__"
ONTOLOGY_DIRECTORY_NAME: str = "ontology"
ONTOLOGY_RESOURCE_DIRECTORY_NAME: str = "resource"
PAYLOAD_DIRECTORY_NAME: str = "payload"
PAYLOAD_SUBDIRECTORY_NAMES: Tuple[str, ...] = (
    "linkset",
    "document",
    "triple",
)


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _required_directories(dataset_path: Path) -> Tuple[Path, ...]:
    ontology_path: Path = dataset_path / ONTOLOGY_DIRECTORY_NAME
    payload_path: Path = dataset_path / PAYLOAD_DIRECTORY_NAME
    payload_subdirectories: Tuple[Path, ...] = tuple(
        payload_path / directory_name
        for directory_name in PAYLOAD_SUBDIRECTORY_NAMES
    )
    return (
        dataset_path / ONTOBDC_DIRECTORY_NAME,
        ontology_path,
        ontology_path / ONTOLOGY_RESOURCE_DIRECTORY_NAME,
        payload_path,
        *payload_subdirectories,
    )


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 when every required dataset directory exists, 1 otherwise."""
    del root_path

    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    required_directories: Tuple[Path, ...] = _required_directories(
        resolved_dataset_path
    )
    return 0 if all(path.is_dir() for path in required_directories) else 1


if __name__ == "__main__":
    raise SystemExit(main())
