from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitContainerFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        config: Dict[str, Any] = InitContainerFiles.read_config(root)
        directory: Any = config.get("directory")
        if not isinstance(directory, dict):
            directory = {}
        root_entry: Any = directory.get("root")
        if not isinstance(root_entry, dict):
            root_entry = {}
        root_entry["absolute_path"] = root
        directory["root"] = root_entry
        config["directory"] = directory
        InitContainerFiles.write_config(root, config)
        return 0
    except Exception:
        return 1
