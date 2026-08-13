from typing import Optional

from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.surface_common import resolve_document, state_reached


def main(surface_path: Optional[str] = None) -> int:
    try:
        _, document = resolve_document(surface_path)
    except Exception:
        return 1
    return (
        0
        if state_reached(document, SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED)
        else 1
    )
