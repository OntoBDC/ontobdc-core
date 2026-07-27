from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_DEFAULT_ENGINE: str = "venv"


def _get_config_file(root_path: Optional[str] = None) -> Path:
    resolved_root_path: Path
    if isinstance(root_path, str) and root_path.strip():
        resolved_root_path = Path(root_path).expanduser().resolve()
    else:
        resolved_root_path = Path.cwd().resolve()

    return resolved_root_path / ".__ontobdc__" / "config.yaml"


def main(root_path: Optional[str] = None) -> int:
    try:
        config_file: Path = _get_config_file(root_path=root_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)

        current_config: Dict[str, Any] = {}
        if config_file.is_file():
            with open(config_file, "r", encoding="utf-8") as file_handle:
                loaded_config: Any = yaml.safe_load(file_handle) or {}

            if isinstance(loaded_config, dict):
                current_config = loaded_config

        engine: object = current_config.get("engine")
        if not isinstance(engine, str) or not engine.strip():
            current_config["engine"] = _DEFAULT_ENGINE

        with open(config_file, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(current_config, file_handle, default_flow_style=False, sort_keys=False)

        return 0
    except Exception:
        return 1
