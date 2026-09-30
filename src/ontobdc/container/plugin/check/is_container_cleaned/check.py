import os
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Set


def find_matching_files(
    container_path: str,
    file_names: Sequence[str],
) -> List[Path]:
    resolved_container_path: Path = Path(container_path).expanduser().resolve()
    if not resolved_container_path.is_dir():
        raise ValueError("The container path is not a directory.")

    normalized_file_names: Set[str] = _normalize_file_names(file_names)
    matching_files: List[Path] = []

    def raise_walk_error(error: OSError) -> None:
        raise error

    for current_root, directory_names, current_file_names in os.walk(
        resolved_container_path,
        topdown=True,
        onerror=raise_walk_error,
        followlinks=False,
    ):
        current_path: Path = Path(current_root)
        directory_names[:] = [
            directory_name
            for directory_name in directory_names
            if not (current_path / directory_name).is_symlink()
        ]

        matching_files.extend(
            current_path / file_name
            for file_name in current_file_names
            if file_name in normalized_file_names
        )

    return sorted(
        matching_files,
        key=lambda file_path: file_path.relative_to(
            resolved_container_path
        ).as_posix(),
    )


def evaluate(
    container_path: str,
    file_names: Sequence[str],
) -> int:
    """
    Return 0 when clean, 1 when matching files remain, and 2 when invalid.
    """
    try:
        matching_files: List[Path] = find_matching_files(
            container_path=container_path,
            file_names=file_names,
        )
    except (OSError, TypeError, ValueError):
        return 2

    return 1 if matching_files else 0


def main(
    print_log: Optional[Callable[..., None]] = None,
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
    file_names: Optional[Sequence[str]] = None,
) -> int:
    del root_path
    if not container_path or file_names is None:
        return 2

    result: int = evaluate(
        container_path=container_path,
        file_names=file_names,
    )
    if print_log is not None and result != 0:
        if result == 2:
            print_log(
                "ERROR",
                "Check Container Cleaned",
                "The container cleanup state could not be evaluated.",
            )
        else:
            print_log(
                "WARNING",
                "Check Container Cleaned",
                "Files configured for cleanup are still present.",
            )

    return result


def _normalize_file_names(file_names: Sequence[str]) -> Set[str]:
    if isinstance(file_names, str):
        raise TypeError("The cleanup file names must be a sequence of names.")

    normalized_file_names: Set[str] = set()
    for file_name in file_names:
        if not isinstance(file_name, str):
            raise TypeError("Each cleanup file name must be a string.")

        normalized_file_name: str = file_name.strip()
        if (
            not normalized_file_name
            or normalized_file_name in {".", ".."}
            or "/" in normalized_file_name
            or "\\" in normalized_file_name
        ):
            raise ValueError(
                "Each cleanup entry must be a plain file name."
            )

        normalized_file_names.add(normalized_file_name)

    if not normalized_file_names:
        raise ValueError("At least one cleanup file name is required.")

    return normalized_file_names
