import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


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

    nodes: Dict[str, Dict[str, Any]] = {
        node["@id"]: node
        for node in graph_data
        if isinstance(node, dict) and isinstance(node.get("@id"), str)
    }
    file_ids: Set[str] = set()
    for part in has_part:
        if not isinstance(part, dict):
            return None
        part_id: object = part.get("@id")
        if not isinstance(part_id, str) or not part_id.strip():
            return None
        # A file is named by its path, or by an identifier whose node says its paths in its history; a
        # file may be at several paths (a copy is the same file).
        node: Optional[Dict[str, Any]] = nodes.get(part_id)
        if CrateFileHistory.is_identifier(part_id) or (node is not None and node.get(CrateFileHistory.LIST_PROPERTY)):
            paths: List[str] = CrateFileHistory.paths_of(node if node is not None else {"@id": part_id})
        else:
            paths = [part_id]
        if not paths:
            return None
        for path in paths:
            normalized_id: str = _normalize_file_id(path)
            if (
                ContainerDataPackageSynchronizer.is_file_blocked_from_publication(Path(normalized_id).name)
                and not ContainerDataPackageSynchronizer.is_hidden_path(normalized_id)
            ):
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
        node_type = node.get("@type")
        if not (node_type == "File" or (isinstance(node_type, list) and "File" in node_type)):
            continue
        paths: List[str] = CrateFileHistory.paths_of(node)
        if not paths:
            continue
        for path in paths:
            normalized_id: str = _normalize_file_id(path)
            if (
                ContainerDataPackageSynchronizer.is_file_blocked_from_publication(Path(normalized_id).name)
                and not ContainerDataPackageSynchronizer.is_hidden_path(normalized_id)
            ):
                continue
            file_nodes[normalized_id] = node

    return file_nodes


def _metadata_problem(files: ContainerFileRepository, file_ids: Set[str], crate_data: Dict[str, Any]) -> Optional[str]:
    """What keeps the file nodes of the RO-Crate from being the files of the container, or None when nothing does."""
    file_nodes = _extract_file_nodes(crate_data)
    if file_nodes is None:
        return "the file nodes of the RO-Crate cannot be read"
    if set(file_nodes) != file_ids:
        return (
            f"the file nodes of the RO-Crate are not the files of the container"
            f"{_difference(file_ids, set(file_nodes), 'only in the container', 'only in the file nodes')}"
        )

    for file_id in sorted(file_ids):
        expected = files.properties(file_id)
        if expected is None:
            # Safe-stat could not read the file even after the central
            # Win32 retry.  Treat it as mismatched metadata: the check
            # returns ``1`` and the hotfix will either produce properties
            # on retry or drop the entry if the file has actually vanished.
            return f"{file_id}: the file cannot be seen"
        node = file_nodes[file_id]
        primary: Optional[str] = CrateFileHistory.path_of(node)
        if primary is None or _normalize_file_id(primary) != file_id:
            # The properties of the node are the ones of the file at its current path; a copy has its own.
            continue
        for key, value in expected.items():
            if node.get(key) != value:
                return f"{file_id}: the node says {key} is {node.get(key)!r}, the file has {value!r}"
    return None


def _difference(left: Set[str], right: Set[str], left_name: str, right_name: str, shown: int = 5) -> str:
    """The paths of each side that the other lacks, a few of them, for a message."""
    parts: List[str] = []
    for names, label in ((left - right, left_name), (right - left, right_name)):
        if names:
            listed: List[str] = sorted(names)
            more: str = f" and {len(listed) - shown} more" if len(listed) > shown else ""
            parts.append(f"{label} ({len(listed)}): {', '.join(repr(name) for name in listed[:shown])}{more}")
    return f" - {'; '.join(parts)}" if parts else ""


def problems(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> List[str]:
    """What keeps the manifest of the container from being in step with it, in words; none when it is."""
    resolved_container_path: Optional[Path] = _resolve_path(container_path)
    resolved_root_path: Optional[Path] = _resolve_path(root_path)
    if resolved_container_path is None or resolved_root_path is None:
        return ["the container or the root of the storage is not given"]

    if check_container_storage_index_ready(
        container_path=str(resolved_container_path),
        root_path=str(resolved_root_path),
    ) != 0:
        return [f"the storage index of {resolved_root_path} does not know the container at {resolved_container_path}"]

    crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(
        resolved_container_path,
    )
    if not crate_file.is_file():
        return [f"there is no RO-Crate metadata at {crate_file}"]

    try:
        crate_data: object = json.loads(crate_file.read_text(encoding="utf-8"))
    except Exception as error:
        return [f"the RO-Crate metadata cannot be read: {error}"]

    if not isinstance(crate_data, dict):
        return ["the RO-Crate metadata is not an object"]

    files: ContainerFileRepository = ContainerFileRepository(resolved_container_path)
    expected_file_ids: Set[str] = set(files.list())
    crate_file_ids: Optional[Set[str]] = _extract_has_part_ids(crate_data)
    if crate_file_ids is None:
        return ["the hasPart of the RO-Crate cannot be read"]
    if crate_file_ids != expected_file_ids:
        return [
            f"the files of the RO-Crate are not the files of the container"
            f"{_difference(expected_file_ids, crate_file_ids, 'only in the container', 'only in the RO-Crate')}"
        ]

    problem: Optional[str] = _metadata_problem(files, expected_file_ids, crate_data)
    if problem is not None:
        return [problem]

    # The history of each file must know it as it is now.
    return CrateFileHistory.mismatches(files, CrateFileHistory.read_all(crate_data), expected_file_ids)


def main(
    container_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    return 1 if problems(container_path, root_path) else 0


if __name__ == "__main__":
    raise SystemExit(main())
