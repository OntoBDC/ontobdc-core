import json
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.manifest import list_container_resource_paths
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)


def is_container_publishable(context: CliContextPort) -> bool:
    """Return whether local publication metadata matches container files."""
    try:
        container_path = _container_path(context)
        root_path = Path(context.root_path).expanduser().resolve()
        if (
            check_container_metadata_ready(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            != 0
        ):
            return False

        descriptor = _load_descriptor(container_path)
        expected_paths = set(list_container_resource_paths(container_path))
        described_paths = set(
            _local_descriptor_paths(container_path, descriptor)
        )
        return expected_paths == described_paths
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _container_path(context: CliContextPort) -> Path:
    value = context.get_parameter_value("container_path")
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("The container path was not resolved.")

    container_path = Path(normalized).expanduser().resolve()
    if not container_path.is_dir():
        raise ValueError(
            f"Container path is not an accessible directory: {container_path}"
        )
    return container_path


def _load_descriptor(container_path: Path) -> Dict[str, Any]:
    datapackage_path = (
        container_path / ".__ontobdc__" / "datapackage.json"
    )
    loaded = json.loads(datapackage_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(
            f"Invalid container datapackage: {datapackage_path}"
        )
    if not isinstance(loaded.get("resources", []), list):
        raise ValueError(
            "Container datapackage resources must be a list."
        )
    return loaded


def _local_descriptor_paths(
    container_path: Path,
    descriptor: Dict[str, Any],
) -> Iterable[str]:
    metadata_dir = container_path / ".__ontobdc__"
    for item in descriptor.get("resources", []):
        if not isinstance(item, dict):
            continue

        path_value = item.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            continue

        normalized_path = path_value.strip()
        candidate = Path(normalized_path)
        parsed = urlparse(normalized_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        elif parsed.scheme.lower() == "file":
            resolved = Path(
                url2pathname(unquote(parsed.path))
            ).expanduser().resolve()
        elif parsed.scheme:
            continue
        else:
            resolved = (metadata_dir / candidate).resolve()

        try:
            yield resolved.relative_to(container_path).as_posix()
        except ValueError:
            continue
