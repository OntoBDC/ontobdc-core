import json
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerRoCrateTreeAdapter:
    """Read-only, isolated reader for a container's RO-Crate manifest.

    Parses ``ro-crate-metadata.json`` directly as JSON and never touches the
    ``rocrate`` package's write path (the check/hotfix machinery that keeps
    the manifest in sync). This adapter only ever reads whatever is already
    on disk, and any failure — missing file, corrupt JSON, unexpected shape
    — yields an empty tree instead of raising, so a stale or absent crate
    never breaks the surrounding container tree view.
    """

    def build_nodes(self, container_path: Path) -> List[Dict[str, Any]]:
        try:
            return self._build_nodes(container_path)
        except Exception:
            return []

    def _build_nodes(self, container_path: Path) -> List[Dict[str, Any]]:
        manifest_path: Path = (
            StorageBootstrap.get_container_crate_metadata_file_path(container_path)
        )
        if not manifest_path.is_file():
            return []

        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            manifest: Dict[str, Any] = json.load(manifest_file)

        graph: List[Dict[str, Any]] = manifest.get("@graph") or []
        root: Dict[str, Any] = {"children": {}}
        for entity in graph:
            if "File" not in self._as_type_list(entity.get("@type")):
                continue
            raw_id: str = str(entity.get("@id") or "").strip()
            if not raw_id:
                continue
            path_parts: List[str] = [
                part for part in unquote(raw_id).split("/") if part
            ]
            if not path_parts:
                continue

            cursor: Dict[str, Any] = root
            for directory_name in path_parts[:-1]:
                cursor = cursor["children"].setdefault(
                    directory_name,
                    {"name": directory_name, "kind": "dir", "children": {}},
                )

            file_name: str = str(entity.get("name") or path_parts[-1])
            cursor["children"][file_name] = {
                "name": file_name,
                "kind": "file",
                "children": {},
            }

        return self._sorted_children(root)

    @staticmethod
    def _as_type_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if value is None:
            return []
        return [str(value)]

    def _sorted_children(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        children: Dict[str, Any] = node.get("children") or {}
        ordered: List[Dict[str, Any]] = sorted(
            children.values(),
            key=lambda child: (
                child.get("kind") != "dir",
                str(child.get("name") or "").lower(),
            ),
        )
        return [
            {
                "name": child.get("name"),
                "kind": child.get("kind"),
                "children": self._sorted_children(child),
            }
            for child in ordered
        ]
