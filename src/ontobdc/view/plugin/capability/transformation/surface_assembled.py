import re
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import (
    MATCHES_ID,
    assemble_surface_markup,
    extract_json_script,
    set_state_marker,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_assembled.check import main as check_surface_assembled


class SurfaceAssembledCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_assembled",
        version="1.0.0",
        name="Surface Assembled",
        description="Compose operation, content and pinned regions with matched Tiles and runtime layout constraints.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "assembly", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ASSEMBLED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ASSEMBLED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_assembled)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        matches = extract_json_script(document, MATCHES_ID)
        if not isinstance(matches, list):
            raise ValueError("Surface matches are missing or invalid")
        document = assemble_surface_markup(document, matches)
        document = re.sub(
            r"<onto-presentation-surface\b(?![^>]*\bdata-ontobdc-assembled=)",
            '<onto-presentation-surface data-ontobdc-assembled="true"',
            document,
            count=1,
            flags=re.IGNORECASE,
        )
        document = set_state_marker(document, "surface_assembled")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_assembled, "surface_assembled")
        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_ASSEMBLED,
            "surface_path": str(path),
            "tile_count": len(matches),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
