from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _get_config_file(root_path: Optional[str] = None) -> Path:
    resolved_root_path: Path = Path(root_path).expanduser().resolve() if isinstance(root_path, str) and root_path.strip() else Path.cwd().resolve()
    return resolved_root_path / ".__ontobdc__" / "config.yaml"


def _build_default_config(root_path: Path) -> Dict[str, Any]:
    return {
        "directory": {
            "root": {
                "absolute_path": str(root_path),
            },
        },
        "engine": "venv",
    }


def main(root_path: Optional[str] = None) -> int:
    try:
        config_file: Path = _get_config_file(root_path=root_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        resolved_root_path: Path = config_file.parent.parent.resolve()
        default_config: Dict[str, Any] = _build_default_config(resolved_root_path)

        current_config: Dict[str, Any] = {}
        if config_file.is_file():
            with open(config_file, "r", encoding="utf-8") as file_handle:
                loaded_config: Any = yaml.safe_load(file_handle) or {}
            if isinstance(loaded_config, dict):
                current_config = loaded_config

        current_directory: Dict[str, Any] = current_config.get("directory", {})
        if not isinstance(current_directory, dict):
            current_directory = {}

        current_root: Dict[str, Any] = current_directory.get("root", {})
        if not isinstance(current_root, dict):
            current_root = {}
        current_root["absolute_path"] = default_config["directory"]["root"]["absolute_path"]
        current_directory["root"] = current_root
        current_config["directory"] = current_directory

        if not isinstance(current_config.get("engine"), str) or not current_config["engine"].strip():
            current_config["engine"] = default_config["engine"]

        with open(config_file, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(current_config, file_handle, default_flow_style=False, sort_keys=False)

        return 0
    except Exception:
        return 1
