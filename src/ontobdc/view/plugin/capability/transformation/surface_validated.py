from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import set_state_marker
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_validated.check import main as check_surface_validated
from ontobdc.view.plugin.check.surface_common import is_valid_surface


class SurfaceValidatedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_validated",
        version="1.0.0",
        name="Surface Validated",
        description="Validate the packaged offline HTML Surface and mark it as validated.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "html", "validation", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_VALIDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_VALIDATED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_validated)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        if not is_valid_surface(document):
            raise ValueError("Surface package failed validation")
        document = set_state_marker(document, "surface_validated")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_validated, "surface_validated")
        return {"resulting_state": SurfaceGenerationProcessState.SURFACE_VALIDATED, "surface_path": str(path)}

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
