from pathlib import Path
from typing import Optional

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


def main(root_path: Optional[str] = None) -> int:
    try:
        root: Path = StorageBootstrap.get_init_root_path(root_path=root_path)
        storage_file: Path = StorageBootstrap.get_storage_file_path(root)
        storage_file.parent.mkdir(parents=True, exist_ok=True)
        StorageBootstrap.build_storage_graph(root).serialize(
            destination=storage_file,
            format="turtle",
        )
        return 0
    except Exception:
        return 1
