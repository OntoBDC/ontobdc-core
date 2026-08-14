import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ContainerResourceInventory:
    """Read the canonical synchronized container datapackage inventory."""

    def __init__(self, container_path: Path) -> None:
        self.container_path = Path(container_path).expanduser().resolve()
        self.path = self.container_path / ".__ontobdc__" / "datapackage.json"

    def list_resources(self) -> list[dict[str, str]]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Container inventory not found: {self.path}")
        payload: Any = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(
            payload.get("resources"), list
        ):
            raise TypeError(f"Invalid container inventory: {self.path}")
        resources: list[dict[str, str]] = []
        for raw in payload["resources"]:
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("path") or "").strip()
            if not path:
                continue
            parsed = urlparse(path)
            if parsed.scheme:
                uri = str(raw.get("uri") or path).strip()
                display_path = path
            else:
                absolute = (self.path.parent / path).resolve()
                try:
                    absolute.relative_to(self.container_path)
                except ValueError:
                    continue
                if ".__ontobdc__" in absolute.parts:
                    continue
                uri = str(raw.get("uri") or absolute.as_uri()).strip()
                display_path = absolute.relative_to(self.container_path).as_posix()
            resources.append(
                {
                    "uri": uri,
                    "title": str(
                        raw.get("title") or raw.get("name") or Path(display_path).name
                    ),
                    "path": display_path,
                    "media_type": str(raw.get("mediatype") or ""),
                    "description": str(raw.get("description") or ""),
                }
            )
        return sorted(resources, key=lambda item: (item["path"], item["uri"]))
