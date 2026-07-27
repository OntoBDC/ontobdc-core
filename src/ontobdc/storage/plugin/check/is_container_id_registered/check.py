
from pathlib import Path
from typing import Optional
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph


def get_registered_container_location(
    container_id: Optional[str] = None,
    root_path: Optional[str] = None,
) -> Optional[Path]:
    if not isinstance(container_id, str) or not container_id.strip():
        return None

    if not isinstance(root_path, str) or not root_path.strip():
        return None

    try:
        storage_graph: LoadedStorageGraph = LoadedStorageGraph(get_storage_file(root_path))
    except Exception:
        return None

    for container in storage_graph.storage_graph.list_containers():
        if not isinstance(container, dict):
            continue

        known_container_id = container.get("id")
        if not isinstance(known_container_id, str) or known_container_id.strip() != container_id.strip():
            continue

        location = container.get("location")
        if not isinstance(location, str) or not location.strip():
            return None

        return Path(location).expanduser().resolve()

    return None


def main(
    container_id: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    if not isinstance(container_id, str) or not container_id.strip():
        return 1

    if not isinstance(root_path, str) or not root_path.strip():
        return 1

    container_location: Optional[Path] = get_registered_container_location(
        container_id=container_id,
        root_path=root_path,
    )
    if container_location is None:
        return 1

    return 0
