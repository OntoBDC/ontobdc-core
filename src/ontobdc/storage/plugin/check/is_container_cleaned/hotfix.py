from pathlib import Path
from typing import Callable, List, Optional, Sequence

from ontobdc.storage.plugin.check.is_container_cleaned.check import (
    find_matching_files,
)


def main(
    print_log: Optional[Callable[..., None]] = None,
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
    file_names: Optional[Sequence[str]] = None,
) -> int:
    del root_path
    if not container_path or file_names is None:
        return 2

    try:
        matching_files: List[Path] = find_matching_files(
            container_path=container_path,
            file_names=file_names,
        )
    except (OSError, TypeError, ValueError) as error:
        if print_log is not None:
            print_log(
                "ERROR",
                "Clean Container",
                str(error),
            )
        return 2

    try:
        for matching_file in matching_files:
            try:
                matching_file.unlink()
            except FileNotFoundError:
                continue
    except OSError as error:
        if print_log is not None:
            print_log(
                "ERROR",
                "Clean Container",
                str(error),
            )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
