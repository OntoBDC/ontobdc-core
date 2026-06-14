
import os
from typing import Any, Dict, Optional

import yaml

from ontobdc.cli import config_data as get_config_data


def _config_path(project_root: str) -> str:
    return os.path.join(project_root, ".__ontobdc__", "config.yaml")


def _load_config(project_root: str) -> Dict[str, Any]:
    config_path = _config_path(project_root)
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_config(project_root: str, config: Dict[str, Any]) -> None:
    config_path = _config_path(project_root)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def is_enabled() -> bool:
    """
    Checks whether the project-local dev tool is enabled.
    """
    config_data: Optional[Dict[str, Any]] = get_config_data()
    if config_data is None:
        return False
    if 'tool' not in config_data.get('dev', {}):
        return False
    if config_data.get('dev', {}).get('tool') != 'enabled':
        return False

    return True


def enable_tool(project_root: str) -> None:
    config = _load_config(project_root)
    config.setdefault("dev", {})["tool"] = "enabled"
    _write_config(project_root, config)


def set_ssh_key_path(project_root: str, ssh_key_path: str) -> None:
    config = _load_config(project_root)
    config.setdefault("dev", {}).setdefault("repo", {}).setdefault("ssh", {})["key_path"] = ssh_key_path
    _write_config(project_root, config)


def get_ssh_key_path(project_root: str) -> str:
    config = _load_config(project_root)
    dev = config.get("dev") or {}
    key_path = (((dev.get("repo") or {}).get("ssh") or {}).get("key_path") or "")
    if not key_path:
        key_path = ((((config.get("repo") or {}).get("ssh") or {}).get("key_path")) or "")

    return key_path if isinstance(key_path, str) else ""


def remove_ssh_key_path(project_root: str) -> None:
    config = _load_config(project_root)
    dev = config.get("dev") or {}
    repo = dev.get("repo") or {}
    ssh = repo.get("ssh") or {}

    ssh.pop("key_path", None)
    if not ssh:
        repo.pop("ssh", None)
    else:
        repo["ssh"] = ssh

    if not repo:
        dev.pop("repo", None)
    else:
        dev["repo"] = repo

    if not dev:
        config.pop("dev", None)
    else:
        config["dev"] = dev

    _write_config(project_root, config)
