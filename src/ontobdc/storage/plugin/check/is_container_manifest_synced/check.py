import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import (
    StorageLayoutConstants,
    StoragePathStatHelper,
    get_container_crate_metadata_file_path,
)
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


_IGNORED_MARKER_DIR_NAMES: Set[str] = {StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME}
_DATASET_MARKER_FILE_NAMES: Set[str] = {
    StorageLayoutConstants.DATASET_STORAGE_FILE_NAME,
    "nid.ttl",
}
_DATASET_LINKSET_DIR_NAME: str = "linkset"
_DATASET_DATAPACKAGE_FILE_NAME: str = "datapackage.json"
_GENERATED_SURFACE_FILE_NAME: str = "index.html"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _is_dataset_dir(candidate_dir: Path) -> bool:
    marker_dir: Path = candidate_dir / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
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
            if ContainerDataPackageSynchronizer.is_file_blocked_from_publication(file_name):
                continue
            file_path: Path = root_path / file_name
            relative_path: str = file_path.relative_to(container_path).as_posix()
            if not relative_path.strip() or relative_path == _GENERATED_SURFACE_FILE_NAME:
                continue
            files.append(relative_path)

    return sorted(set(files))


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _expected_file_properties(file_path: Path) -> Optional[Dict[str, Any]]:
    """Return expected crate-metadata properties, or ``None`` when the file
    truly cannot be statted even after the central Win32 retry.

    Returning ``None`` here instead of raising avoids spurious check
    crashes for files whose names trigger Win32 trailing-dot / MAX_PATH
    oddities between ``os.walk`` and ``stat``.  The caller
    ``_metadata_matches`` treats ``None`` the same as a metadata mismatch,
    which returns ``1`` and correctly triggers the hotfix so the manifest
    is rewritten with the stat that finally succeeds via the extended-path
    retry in hotfix.py.
    """
    stat_result = StoragePathStatHelper.safe_stat(file_path)
    if stat_result is None:
        return None

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


def _normalize_file_id(raw_id: str) -> str:
    normalized_id = unquote(raw_id.strip())
    if normalized_id.startswith("./"):
        normalized_id = normalized_id[2:]
    return normalized_id


def _extract_has_part_ids(crate_data: Dict[str, Any]) -> Optional[Set[str]]:
    graph_data: object = crate_data.get("@graph")
    if not isinstance(graph_data, list):
        return None

    dataset_node: Optional[Dict[str, Any]] = None
    for node in graph_data:
        if isinstance(node, dict) and node.get("@id") == "./":
            dataset_node = node
            break

    if dataset_node is None:
        return None

    has_part: object = dataset_node.get("hasPart")
    if has_part is None:
        return set()
    if not isinstance(has_part, list):
        return None

    file_ids: Set[str] = set()
    for part in has_part:
        if not isinstance(part, dict):
            return None
        part_id: object = part.get("@id")
        if not isinstance(part_id, str) or not part_id.strip():
            return None
        normalized_id: str = _normalize_file_id(part_id)
        if ContainerDataPackageSynchronizer.is_file_blocked_from_publication(Path(normalized_id).name):
            continue
        file_ids.add(normalized_id)

    return file_ids


def _extract_file_nodes(crate_data: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
    graph_data: object = crate_data.get("@graph")
    if not isinstance(graph_data, list):
        return None

    file_nodes: Dict[str, Dict[str, Any]] = {}
    for node in graph_data:
        if not isinstance(node, dict):
            continue
        node_id = node.get("@id")
        if not isinstance(node_id, str) or node_id in {"./", "ro-crate-metadata.json"}:
            continue
        normalized_id: str = _normalize_file_id(node_id)
        if ContainerDataPackageSynchronizer.is_file_blocked_from_publication(Path(normalized_id).name):
            continue
        node_type = node.get("@type")
        if node_type == "File" or (isinstance(node_type, list) and "File" in node_type):
            file_nodes[normalized_id] = node

    return file_nodes


def _metadata_matches(container_path: Path, file_ids: Set[str], crate_data: Dict[str, Any]) -> bool:
    file_nodes = _extract_file_nodes(crate_data)
    if file_nodes is None or set(file_nodes) != file_ids:
        return False

    for file_id in file_ids:
        expected = _expected_file_properties(container_path / Path(file_id))
        if expected is None:
            # Safe-stat could not read the file even after the central
            # Win32 retry.  Treat it as mismatched metadata: the check
            # returns ``1`` and the hotfix will either produce properties
            # on retry or drop the entry if the file has actually vanished.
            return False
        node = file_nodes[file_id]
        for key, value in expected.items():
            if node.get(key) != value:
                return False
    return True


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

    crate_file: Path = get_container_crate_metadata_file_path(resolved_container_path)
    if not crate_file.is_file():
        return 1

    try:
        crate_data: object = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception:
        return 1

    if not isinstance(crate_data, dict):
        return 1

    expected_file_ids: Set[str] = set(_iter_container_files(resolved_container_path))
    crate_file_ids: Optional[Set[str]] = _extract_has_part_ids(crate_data)
    if crate_file_ids is None or crate_file_ids != expected_file_ids:
        return 1

    if not _metadata_matches(resolved_container_path, expected_file_ids, crate_data):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
