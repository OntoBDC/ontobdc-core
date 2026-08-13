from typing import Any, Dict, List, Set

from rdflib import Graph

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.context import surface_layouts_path_from_context
from ontobdc.view.adapter.surface.document import (
    DEFAULT_LAYOUTS_ID,
    MATCHES_ID,
    embed_default_layouts_bootstrap,
    extract_json_script,
    normalize_matches,
    set_state_marker,
    upsert_json_script,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_operational_matched.check import (
    main as check_surface_operational_matched,
)

# `ontobdc_view` (repo `presentation`) already owns the RDF `SurfaceDefinition`/
# `DefaultSurfaceLayout` parser and JSON-payload resolver (cloud.md/claude2.md).
# `ontobdc` already runtime-depends on `ontobdc_view` being installed without a
# formal pyproject dependency — see `SurfacePackagedCapability._read_component_sources`
# (bare `import ontobdc_view`) and `ComponentLoader._load_ontobdc_view_components`
# (dynamic `importlib.import_module("ontobdc_view.component.plugin")`) — this
# reuses that same established, one-way pattern rather than duplicating the
# parser here.
from ontobdc_view.component.adapter.surface_definition import (
    default_surface_layouts,
    parse_default_surface_layouts,
)
from ontobdc_view.component.adapter.surface_resolution import to_render_payload


class SurfaceOperationalMatchedCapability(TransformationCapability):
    """Match operational (OperationRegion) Tiles declared by RDF layouts.

    `SURFACE_MATCHED` only ever auto-matches *content* Tiles (entities
    marked `obdc:SurfaceableEntity`) or Tiles the caller explicitly
    requested — nothing ever populates the OperationRegion (logo/theme/
    language/...) on its own. This stage closes that gap: whichever
    `view:DefaultSurfaceLayout`/`view:PresentationSurface` RDF the container
    configures (`surface_layouts_path_from_context`) is used; if it
    configures none, `ontobdc_view.default_surface_layouts()` — a shipped
    fallback (Logo/Language/Theme in an unbounded OperationRegion) — applies
    instead, so a container with no configuration at all still gets a
    sensible operational Surface rather than an empty one. Every declared
    `ComponentPlacement` in an `OperationRegion`, across every candidate
    layout, is resolved to a registered Component and added to the existing
    matches list — skipping any tag the caller already requested explicitly,
    so an explicit request always wins.

    This offline generator has no notion of the eventual browser viewport
    (`standard_surface_html.yaml`'s own description says so) — it embeds
    *every* candidate layout's resolved JSON (`DEFAULT_LAYOUTS_ID`) plus a
    small bootstrap script that hands them to
    `onto-presentation-surface.defaultSurfaceLayouts`; which one applies is
    selected entirely client-side, at whatever capacity the browser
    eventually measures.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_operational_matched",
        version="1.0.0",
        name="Surface Operational Matched",
        description="Match operational Tiles declared by DefaultSurfaceLayout/PresentationSurface RDF and embed the resolved candidates for client-side selection.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "operational", "default-layout", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()
        self._components = ComponentLoader()

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

        candidate_layouts = self._candidate_layouts(context)
        injected = self._injected_operational_matches(candidate_layouts, matches)

        all_matches = normalize_matches(matches + injected)
        document = upsert_json_script(document, MATCHES_ID, all_matches)

        if candidate_layouts:
            payloads = [to_render_payload(layout, self._components) for layout in candidate_layouts]
            document = upsert_json_script(document, DEFAULT_LAYOUTS_ID, payloads)
            document = embed_default_layouts_bootstrap(document)

        document = set_state_marker(document, "surface_operational_matched")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_operational_matched, "surface_operational_matched")

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_OPERATIONAL_MATCHED,
            "surface_path": str(path),
            "operational_match_count": len(injected),
            "default_layout_count": len(candidate_layouts),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _candidate_layouts(self, context: CliContextPort) -> List:
        layouts_path = surface_layouts_path_from_context(context)
        if layouts_path is None or not layouts_path.is_file():
            # No project-specific layouts configured — fall back to the
            # shipped default rather than leaving the OperationRegion empty.
            return default_surface_layouts()

        graph = Graph()
        graph.parse(str(layouts_path), format="turtle")
        return parse_default_surface_layouts(graph)

    def _injected_operational_matches(
        self,
        candidate_layouts: List,
        existing_matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        seen_tags: Set[str] = {
            str(match.get("tile", "")).strip()
            for match in existing_matches
            if isinstance(match, dict)
        }

        injected: List[Dict[str, Any]] = []
        for layout in candidate_layouts:
            for region in layout.regions:
                if region.role != "OperationRegion":
                    continue
                for placement in region.placements:
                    match = self._resolve_placement_match(placement, seen_tags)
                    if match is None:
                        continue
                    seen_tags.add(match["tile"])
                    injected.append(match)

        return injected

    def _resolve_placement_match(self, placement, seen_tags: Set[str]):
        if not placement.component_type_iri:
            raise ValueError(
                f"ComponentPlacement {placement.iri} has no rdf:type to resolve an operational Tile from"
            )

        resolved = self._components.match_tile_class(placement.component_type_iri)
        if not resolved:
            raise ValueError(f"No registered Component implements {placement.component_type_iri}")

        metadata = resolved[0].METADATA
        if metadata.tag in seen_tags:
            return None

        return {
            "tile": metadata.tag,
            "region": "operation",
            "tileClass": placement.component_type_iri,
            "minColumns": metadata.min_columns,
            "preferredColumns": metadata.min_columns,
            "maxColumns": metadata.max_columns if metadata.max_columns is not None else metadata.min_columns,
            "minRows": 1,
            "preferredRows": 1,
            "maxRows": 1,
            "closed": bool(metadata.default_closed),
        }
