from pathlib import Path
from typing import Optional

from ontobdc.view.adapter.surface.document import resolve_surface_path

_ASSET_DIR = (".__ontobdc__", "asset", "work_stream_view")


def script_path(container_path: Path, script_name: str) -> Path:
    return container_path.joinpath(*_ASSET_DIR, f"{script_name}.js")


def script_is_fresh(surface_path: Optional[str], script_name: str) -> bool:
    """A generated work_stream_view script "counts" once it exists and is
    at least as new as the container's own `index.html` — regenerating the
    Surface (which touches `index.html`) makes every previously-generated
    script stale again, forcing this state (and the ones after it) to
    re-run rather than silently keeping content from an older container.
    """
    index_path = resolve_surface_path(surface_path)
    target = script_path(index_path.parent, script_name)
    try:
        if not target.is_file():
            return False
        if not index_path.is_file():
            return True
        return target.stat().st_mtime >= index_path.stat().st_mtime
    except OSError:
        return False
