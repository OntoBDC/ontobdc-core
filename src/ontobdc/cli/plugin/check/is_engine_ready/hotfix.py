from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitProjectFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

DEFAULT_ENGINE: str = "venv"


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        config: Dict[str, Any] = InitProjectFiles.read_config(root)
        engine: object = config.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            config["engine"] = DEFAULT_ENGINE
        InitProjectFiles.write_config(root, config)
        return 0
    except Exception:
        return 1
