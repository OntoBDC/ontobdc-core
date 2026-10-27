from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitContainerFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

REQUIRED_KEYS = ("name", "mark_svg", "logotype_svg", "slogan")


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        brand: Any = InitContainerFiles.read_config(root).get("brand")
        if not isinstance(brand, dict):
            return 1

        for key in REQUIRED_KEYS:
            value: object = brand.get(key)
            if not isinstance(value, str) or not value.strip():
                return 1

        return 0
    except Exception:
        return 1
