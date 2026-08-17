from typing import Any, Dict, List, Optional, cast

from rdflib import Graph

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import (
    MATCHES_ID,
    extract_json_script,
    normalize_matches,
    set_state_marker,
    upsert_json_script,
    upsert_raw_script,
)
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.capability.transformation.surface_matched import SurfaceMatchedCapability
from ontobdc.view.plugin.check.is_surface_operational_matched.check import (
    main as check_surface_operational_matched,
)

DEFAULT_LAYOUTS_SCRIPT_ID = "ontobdc-surface-default-layouts"
DEFAULT_LAYOUTS_BOOTSTRAP_ID = "ontobdc-surface-default-layouts-bootstrap"

# `whenDefined` makes this independent of where the script tag lands in the
# document relative to the `onto-presentation-surface` element's own
# defining module script — no insertion-order assumption is needed.
_BOOTSTRAP_JS = f"""\
customElements.whenDefined("onto-presentation-surface").then(() => {{
  const dataEl = document.getElementById("{DEFAULT_LAYOUTS_SCRIPT_ID}");
  const surfaceEl = document.querySelector("onto-presentation-surface");
  if (!dataEl || !surfaceEl) return;
  try {{
    surfaceEl.defaultSurfaceLayouts = JSON.parse(dataEl.textContent);
  }} catch (error) {{
    console.error("Failed to apply OntoBDC defaultSurfaceLayouts", error);
  }}
}});
"""


class SurfaceOperationalMatchedCapability(SurfaceMatchedCapability):
    """Resolve the OperationRegion of the shipped `ontobdc_view` DefaultSurfaceLayout.

    `ontobdc_view.component.adapter.surface_definition.default_surface_layouts()`
    ships one always-matching `view:DefaultSurfaceLayout` (Logo/Language/Theme
    in its OperationRegion) — used whenever the caller declared no explicit
    operation-region Tile of its own. Reuses `SurfaceMatchedCapability`'s
    `_with_resolved_tile` (the same Chrome-Tile `tileClass` resolution
    `SURFACE_MATCHED` already implements) to turn each placement into a
    resolved `surface_matches` entry, and additionally embeds the resolved
    `SurfaceDefinition` payload so the browser's own ontology-driven
    `defaultSurfaceLayouts` selection (`onto-presentation-surface.js`,
    `ontobdc-view` >= 0.3) picks it up instead of falling back to the legacy
    fixed topology.

    `ontobdc_view` is not a formal runtime dependency of `ontobdc` (see
    `ontobdc_view`'s own changelog) — this capability is a no-op, not a hard
    failure, whenever it is not installed.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_operational_matched",
        version="1.0.0",
        name="Surface Operational Matched",
        description=(
            "Resolve the OperationRegion of the shipped ontobdc_view DefaultSurfaceLayout "
            "(Logo/Language/Theme) when the caller declared no explicit operation-region "
            "Tile, and embed its SurfaceDefinition for client-side ontology-driven selection."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "operation", "default-layout", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Operation-region defaults were resolved when no explicit tile "
                    "was declared, with Surface definitions embedded for client-side "
                    "selection."
                ),
            },
            "debug_entry": {
                "en": (
                    "Resolving operation-region defaults and embedding Surface "
                    "definitions for client-side selection."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_OPERATIONAL_MATCHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_OPERATIONAL_MATCHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_operational_matched)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        document = self._surface.read(context)
        matches = extract_json_script(document, MATCHES_ID)
        if not isinstance(matches, list):
            raise ValueError("Surface matches are missing or invalid")

        layouts = self._default_layouts()
        operation_already_declared = any(
            str(item.get("region", "")).strip().lower() == "operation" for item in matches
        )

        added: List[Dict[str, Any]] = []
        if layouts and not operation_already_declared:
            empty_graph = Graph()
            for request in self._operation_requests(layouts):
                resolved: Optional[Dict[str, Any]] = self._with_resolved_tile(
                    empty_graph, request, strict=False
                )
                if resolved is not None:
                    added.append(resolved)

        if added:
            matches = normalize_matches(list(matches) + added)
            document = upsert_json_script(document, MATCHES_ID, matches)

        if layouts:
            from ontobdc_view.component.adapter.surface_resolution import to_render_payload

            payload = [to_render_payload(layout) for layout in layouts]
            document = upsert_json_script(document, DEFAULT_LAYOUTS_SCRIPT_ID, payload)
            document = upsert_raw_script(
                document, DEFAULT_LAYOUTS_BOOTSTRAP_ID, "module", _BOOTSTRAP_JS
            )

        document = set_state_marker(document, "surface_operational_matched")
        path = self._surface.write(context, document)
        self._surface.require_check(
            context, check_surface_operational_matched, "surface_operational_matched"
        )

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_OPERATIONAL_MATCHED,
            "surface_path": str(path),
            "operational_match_count": len(added),
            "default_layout_count": len(layouts),
        }

    @staticmethod
    def _default_layouts() -> List[Any]:
        try:
            from ontobdc_view.component.adapter.surface_definition import default_surface_layouts
        except ImportError:
            return []
        return default_surface_layouts()

    @staticmethod
    def _operation_requests(layouts: List[Any]) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        for layout in layouts:
            for region in layout.regions:
                if region.role != "OperationRegion":
                    continue
                for placement in region.placements:
                    if not placement.component_type_iri:
                        continue
                    requests.append(
                        {"tileClass": placement.component_type_iri, "region": "operation"}
                    )
        return requests
