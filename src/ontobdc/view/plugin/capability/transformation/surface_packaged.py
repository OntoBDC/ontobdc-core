from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
from ontobdc.view.adapter.surface.document import (
    MATCHES_ID,
    SURFACE_TAG,
    embed_component_scripts,
    extract_json_script,
    set_state_marker,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_packaged.check import main as check_surface_packaged


class SurfacePackagedCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_packaged",
        version="1.0.0",
        name="Surface Packaged",
        description=(
            "Embed every browser component implementation required by the "
            "Surface for offline execution."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "view",
            "surface",
            "html",
            "offline",
            "packaging",
            "transformation",
        ],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Browser component implementations required by the Surface were "
                    "embedded for offline execution."
                ),
            },
            "debug_entry": {
                "en": (
                    "Embedding required Surface Browser component implementations "
                    "for offline execution."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()
        self._context_adapter = SurfaceContextAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PACKAGED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PACKAGED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_packaged)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        scripts = self._context_adapter.component_scripts(context)
        if not scripts:
            scripts = self._read_component_sources(document)
        if not scripts:
            raise ValueError(
                "No complete build-ready Surface component set was available. "
                "Install ontobdc-view with build-ready components or provide "
                "surface_component_scripts."
            )

        document = embed_component_scripts(document, scripts)
        document = set_state_marker(document, "surface_packaged")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_packaged, "surface_packaged")
        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_PACKAGED,
            "surface_path": str(path),
            "component_script_count": len(scripts),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _required_component_tags(self, document: str) -> List[str]:
        tags = [SURFACE_TAG]
        matches = extract_json_script(document, MATCHES_ID)
        if isinstance(matches, list):
            for item in matches:
                if not isinstance(item, dict):
                    continue
                tile = str(item.get("tile", "")).strip()
                if tile and tile not in tags:
                    tags.append(tile)
        return tags

    def _read_component_sources(self, document: str) -> List[str]:
        try:
            import ontobdc_view
        except Exception:
            return []

        scripts: List[str] = []
        for tag in self._required_component_tags(document):
            try:
                source = ontobdc_view.component_source(tag)
            except Exception:
                return []
            if not isinstance(source, str) or not source.strip():
                return []
            scripts.append(source)
        return scripts
