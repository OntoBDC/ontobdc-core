from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ontobdc.shared.adapter.config import ConfigDataAdapter


def _get_config_file(root_path: Optional[str] = None) -> Path:
    if isinstance(root_path, str) and root_path.strip():
        return Path(root_path).expanduser().resolve() / ".__ontobdc__" / "config.yaml"

    return ConfigDataAdapter().config_file


def main(root_path: Optional[str] = None) -> int:
    try:
        config_file: Path = _get_config_file(root_path=root_path)
        if not config_file.is_file():
            return 1

        with open(config_file, "r", encoding="utf-8") as file_handle:
            parsed_config: Any = yaml.safe_load(file_handle) or {}

        if not isinstance(parsed_config, dict) or len(parsed_config) == 0:
            return 1

        config_adapter: ConfigDataAdapter = ConfigDataAdapter(str(config_file.parent.parent.resolve()))
        config_data: Optional[Dict[str, Any]] = config_adapter.all
        if not isinstance(config_data, dict) or len(config_data) == 0:
            return 1

        directory: Any = config_data.get("directory")
        if not isinstance(directory, dict):
            return 1

        root: Any = directory.get("root")
        if not isinstance(root, dict):
            return 1

        absolute_path: Any = root.get("absolute_path")
        if not isinstance(absolute_path, str) or not absolute_path.strip():
            return 1

        return 0
    except Exception:
        return 1
