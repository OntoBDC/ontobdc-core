from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import make_initial_html, set_state_marker
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_initialized.check import main as check_surface_initialized


class SurfaceInitializedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_initialized",
        version="1.0.0",
        name="Surface Initialized",
        description="Create the minimal offline HTML Presentation Surface document.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "html", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_INITIALIZED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_INITIALIZED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_initialized)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        path = self._surface.path(context)
        lang = str(context.get_parameter_value("language") or "en")
        document = set_state_marker(make_initial_html(lang), "surface_initialized")
        self._surface.write(context, document)
        self._surface.require_check(context, check_surface_initialized, "surface_initialized")
        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_INITIALIZED,
            "surface_path": str(path),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
