from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.shared.adapter.config import ConfigDataAdapter

_REQUIRED_KEYS = ("name", "mark_svg", "logotype_svg", "slogan")


def _make_config_adapter(root_path: Optional[str] = None) -> ConfigDataAdapter:
    if isinstance(root_path, str) and root_path.strip():
        resolved_root_path: Path = Path(root_path).expanduser().resolve()
        return ConfigDataAdapter(root_dir=str(resolved_root_path))

    return ConfigDataAdapter()


def main(root_path: Optional[str] = None) -> int:
    try:
        config_adapter: ConfigDataAdapter = _make_config_adapter(root_path=root_path)
        if not config_adapter.path.is_file():
            return 1

        config_data: Optional[Dict[str, Any]] = config_adapter.all
        if not isinstance(config_data, dict):
            return 1

        brand: object = config_data.get("brand")
        if not isinstance(brand, dict):
            return 1

        for key in _REQUIRED_KEYS:
            value: object = brand.get(key)
            if not isinstance(value, str) or not value.strip():
                return 1

        return 0
    except Exception:
        return 1
