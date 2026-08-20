from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Same shipped defaults as ontobdc_view.component.adapter.source._BRAND --
# kept as a local, self-contained copy (this module has no dependency on
# ontobdc_view) so a freshly-seeded config.yaml always starts from a real,
# renderable brand instead of a placeholder that would need replacing
# before anything shows up.
_DEFAULT_BRAND: Dict[str, str] = {
    "name": "OntoBDC",
    "mark_svg": (
        '<svg viewBox="0 0 64 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="25" fill="none" stroke="currentColor" stroke-width="8"/>'
        '<circle cx="32" cy="32" r="7" fill="currentColor"/></svg>'
    ),
    "logotype_svg": (
        '<svg viewBox="0 0 260 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="23" fill="none" stroke="var(--onto-theme-accent, currentColor)" stroke-width="7"/>'
        '<circle cx="32" cy="32" r="6" fill="var(--onto-theme-accent, currentColor)"/>'
        '<text x="68" y="42" fill="currentColor" font-family="system-ui, sans-serif" '
        'font-size="31" font-weight="700">OntoBDC</text></svg>'
    ),
    "slogan": "Data with Brains",
}


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

        brand: object = current_config.get("brand")
        if not isinstance(brand, dict):
            brand = {}

        for key, default_value in _DEFAULT_BRAND.items():
            value: object = brand.get(key)
            if not isinstance(value, str) or not value.strip():
                brand[key] = default_value

        current_config["brand"] = brand

        with open(config_file, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(current_config, file_handle, default_flow_style=False, sort_keys=False)

        return 0
    except Exception:
        return 1
