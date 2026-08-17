import mimetypes
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rocrate.rocrate import ROCrate

from ontobdc.storage.adapter.bootstrap import (
    ONTOBDC_DIRECTORY_NAME,
    ensure_ontobdc_directory,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


_IGNORED_MARKER_DIR_NAMES: Set[str] = {ONTOBDC_DIRECTORY_NAME}
_DATASET_MARKER_FILE_NAMES: Set[str] = {"dataset.ttl", "nid.ttl"}
_DATASET_LINKSET_DIR_NAME: str = "linkset"
_DATASET_DATAPACKAGE_FILE_NAME: str = "datapackage.json"
# Generated Surface output, not source content — matches check.py's exclusion.
_GENERATED_SURFACE_FILE_NAME: str = "index.html"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _is_dataset_dir(candidate_dir: Path) -> bool:
    marker_dir: Path = candidate_dir / ONTOBDC_DIRECTORY_NAME
    if marker_dir.is_dir():
        for file_name in _DATASET_MARKER_FILE_NAMES:
            if (marker_dir / file_name).is_file():
                return True

    datapackage_file: Path = candidate_dir / _DATASET_LINKSET_DIR_NAME / _DATASET_DATAPACKAGE_FILE_NAME
    return datapackage_file.is_file()


def _iter_container_files(container_path: Path) -> List[str]:
    files: List[str] = []
    for root, dir_names, file_names in os.walk(container_path, topdown=True):
        root_path: Path = Path(root)
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in _IGNORED_MARKER_DIR_NAMES
            and not _is_dataset_dir(root_path / dir_name)
        ]

        for file_name in file_names:
            file_path: Path = root_path / file_name
            relative_path: str = file_path.relative_to(container_path).as_posix()
            if not relative_path.strip() or relative_path == _GENERATED_SURFACE_FILE_NAME:
                continue
            files.append(relative_path)

    return sorted(set(files))


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _file_properties(file_path: Path) -> Dict[str, Any]:
    """Return filesystem metadata available without reading file content."""
    stat_result = file_path.stat()
    properties: Dict[str, Any] = {
        "name": file_path.name,
        "contentSize": str(stat_result.st_size),
        "dateModified": _iso_utc(stat_result.st_mtime),
    }

    media_type, _ = mimetypes.guess_type(file_path.name)
    if media_type:
        properties["encodingFormat"] = media_type

    birth_time = getattr(stat_result, "st_birthtime", None)
    if birth_time is None and os.name == "nt":
        birth_time = stat_result.st_ctime
    if birth_time is not None:
        properties["dateCreated"] = _iso_utc(float(birth_time))

    return properties


def _write_crate_manifest(marker_path: Path, container_path: Path, file_ids: List[str]) -> None:
    crate: ROCrate = ROCrate(gen_preview=False)
    for file_id in file_ids:
        file_path = container_path / Path(file_id)
        crate.add_file(
            source=None,
            dest_path=file_id,
            properties=_file_properties(file_path),
        )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"No source for .*")
        crate.write(marker_path)


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return 1

    if check_container_storage_index_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return 1

    marker_path: Path = ensure_ontobdc_directory(resolved_container_path)
    file_ids: List[str] = _iter_container_files(resolved_container_path)
    _write_crate_manifest(marker_path, resolved_container_path, file_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
