from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.context import component_scripts_from_context
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


_BUILD_PLACEHOLDER = "__ONTOBDC_BUILD_"

# Tags whose packaged JS needs a build-time payload resolved first — plain
# `read_component()` would return the raw template with the placeholder
# still in it. Maps the custom-element tag to the `ontobdc_view` builder
# that produces the ready-to-embed source with project defaults.
_BUILDER_NAME_BY_TAG: Dict[str, str] = {
    "onto-logo-tile": "build_logo_tile",
    "onto-theme-tile": "build_theme_tile",
    "onto-language-tile": "build_language_tile",
    "onto-photo-tile": "build_photo_tile",
}


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
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PACKAGED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_PACKAGED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_packaged)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        scripts = component_scripts_from_context(context)
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
            source = self._build_component_source(ontobdc_view, tag)
            if source is None:
                return []
            scripts.append(source)
        return scripts

    def _build_component_source(self, ontobdc_view: Any, tag: str) -> Optional[str]:
        builder_name = _BUILDER_NAME_BY_TAG.get(tag)
        if builder_name is not None:
            builder = getattr(ontobdc_view, builder_name, None)
            if builder is None:
                return None
            try:
                return str(builder())
            except Exception:
                return None

        try:
            source = ontobdc_view.read_component(f"{tag}.js")
        except Exception:
            return None

        if not isinstance(source, str) or not source.strip():
            return None
        if _BUILD_PLACEHOLDER in source:
            # A component with an unresolved build-time placeholder and no
            # known builder above must be supplied already built through
            # context — silently embedding the raw template would ship a
            # broken component.
            return None

        return source
