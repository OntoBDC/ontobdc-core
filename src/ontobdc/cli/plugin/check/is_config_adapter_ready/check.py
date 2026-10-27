from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitContainerFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        config: Dict[str, Any] = InitContainerFiles.read_config(root)
        directory: Any = config.get("directory")
        root_entry: Any = directory.get("root") if isinstance(directory, dict) else None
        absolute_path: Any = (
            root_entry.get("absolute_path") if isinstance(root_entry, dict) else None
        )
        return 0 if isinstance(absolute_path, str) and absolute_path.strip() else 1
    except Exception:
        return 1
