from typing import Any, Dict, Optional

from ontobdc.cli.adapter.init_config import InitProjectFiles
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

DEFAULT_BRAND: Dict[str, str] = {
    "name": "OntoBDC",
    "mark_svg": (
        '<svg viewBox="0 0 64 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="25" fill="none" '
        'stroke="currentColor" stroke-width="8"/>'
        '<circle cx="32" cy="32" r="7" fill="currentColor"/></svg>'
    ),
    "logotype_svg": (
        '<svg viewBox="0 0 260 64" aria-hidden="true">'
        '<circle cx="32" cy="32" r="23" fill="none" '
        'stroke="var(--onto-theme-accent, currentColor)" stroke-width="7"/>'
        '<circle cx="32" cy="32" r="6" fill="var(--onto-theme-accent, currentColor)"/>'
        '<text x="68" y="42" fill="currentColor" '
        'font-family="system-ui, sans-serif" font-size="31" '
        'font-weight="700">OntoBDC</text></svg>'
    ),
    "slogan": "Data with Brains",
}


def main(root_path: Optional[str] = None) -> int:
    try:
        root: str = str(StorageBootstrap.get_init_root_path(root_path=root_path))
        config: Dict[str, Any] = InitProjectFiles.read_config(root)
        brand: Any = config.get("brand")
        if not isinstance(brand, dict):
            brand = {}
        for key, default_value in DEFAULT_BRAND.items():
            value: object = brand.get(key)
            if not isinstance(value, str) or not value.strip():
                brand[key] = default_value
        config["brand"] = brand
        InitProjectFiles.write_config(root, config)
        return 0
    except Exception:
        return 1
