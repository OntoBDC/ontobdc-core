from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitContainerFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        config: Dict[str, Any] = InitContainerFiles.read_config(root)
        engine: object = config.get("engine")
        return 0 if isinstance(engine, str) and engine.strip() else 1
    except Exception:
        return 1
