from typing import Optional

from ontobdc.view.plugin.check.surface_common import has_initialized_surface, resolve_document


def main(surface_path: Optional[str] = None) -> int:
    try:
        _, document = resolve_document(surface_path)
    except Exception:
        return 1
    return 0 if has_initialized_surface(document) else 1
