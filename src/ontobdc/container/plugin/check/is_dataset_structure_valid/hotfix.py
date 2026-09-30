from pathlib import Path
from typing import Optional, Tuple

from ontobdc.container.plugin.check.is_dataset_structure_valid.check import (
    _required_directories,
    _resolve_path,
)


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Create missing dataset directories and return their resulting health."""
    del root_path

    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    required_directories: Tuple[Path, ...] = _required_directories(
        resolved_dataset_path
    )
    try:
        required_directory: Path
        for required_directory in required_directories:
            required_directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return 1

    return 0 if all(path.is_dir() for path in required_directories) else 1


if __name__ == "__main__":
    raise SystemExit(main())
