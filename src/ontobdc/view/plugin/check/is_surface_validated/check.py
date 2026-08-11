from typing import Optional

from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.surface_common import is_valid_surface, resolve_document, state_reached


def main(surface_path: Optional[str] = None) -> int:
    try:
        _, document = resolve_document(surface_path)
    except Exception:
        return 1
    return 0 if state_reached(document, SurfaceGenerationProcessState.SURFACE_VALIDATED) and is_valid_surface(document) else 1
