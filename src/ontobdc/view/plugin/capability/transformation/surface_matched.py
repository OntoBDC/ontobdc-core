import math
from typing import Any, Dict, List, Optional, Type

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort
from ontobdc.storage.adapter.bootstrap import OBDC
from ontobdc.view.adapter.surface.context import surface_matches_from_context
from ontobdc.view.adapter.surface.document import (
    MATCHES_ID,
    normalize_matches,
    set_state_marker,
    upsert_json_script,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.capability.transformation.data_gathered import DataGatheredCapability
from ontobdc.view.plugin.check.is_surface_matched.check import main as check_surface_matched


class SurfaceMatchedCapability(TransformationCapability):
    """Match presentation requests to registered Components.

    Each request in `surface_matches_from_context` declares a `region` plus
    an optional spatial envelope — but no longer a `tile`. `tile` is
    resolved one of two ways, matching the two Tile kinds `view.ttl`
    describes:

    - Content Tile request (has `data`, an entity reference): resolved via
      `ComponentLoader.match(graph, entity)` — which registered Component's
      `required_uris` (domain `ns.ttl` types/properties) the entity
      satisfies.
    - Chrome Tile request (no `data`, e.g. logo/theme/language — has
      `tileClass` instead): resolved via `ComponentLoader.match_tile_class`
      — there is no entity to infer anything from, so the request names the
      wanted `view.ttl` Tile class directly.

    A request satisfied by no Component, or by neither `data` nor
    `tileClass`, is a hard error — not a silent skip.

    When the caller supplies no requests at all, every DATA_GATHERED entity
    whose rdf:type is explicitly marked `obdc:SurfaceableEntity` — and that
    a registered Component's `required_uris` is also satisfied by — is
    placed automatically (`_auto_matched_requests`) — this is what lets a
    bare `ontobdc view` surface content (e.g. the container's own summary
    Tile) without the caller having to hand-author a `surface_matches`
    request. `required_uris` says how to render an entity; the
    `SurfaceableEntity` marker is the separate decision of whether it
    should appear unprompted at all — a Component can exist for a class
    that never auto-surfaces (e.g. something only ever opened on demand).
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_matched",
        version="1.0.0",
        name="Surface Matched",
        description="Match presentation data to compatible Component definitions and support envelopes.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "component", "matching", "transformation"],
        supported_languages=["en", "pt-br"],
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()
        self._components = ComponentLoader()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_matched)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph = self._gathered_graph(context)
        requests = surface_matches_from_context(context) or self._auto_matched_requests(graph)
        resolved_requests = [
            self._with_resolved_tile(graph, request) for request in requests
        ]
        matches = normalize_matches(resolved_requests)

        document = upsert_json_script(self._surface.read(context), MATCHES_ID, matches)
        document = set_state_marker(document, "surface_matched")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_matched, "surface_matched")

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_MATCHED,
            "surface_path": str(path),
            "match_count": len(matches),
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _gathered_graph(self, context: CliContextPort) -> Graph:
        path = DataGatheredCapability.state_path(context)
        graph = Graph()
        graph.parse(str(path), format="json-ld")
        return graph

    # Auto-match order is a presentation decision, not something RDF graph
    # iteration order should be trusted for (it's an implementation detail
    # of the store, not a documented guarantee) — the container and file
    # tree are the surface's fixed start, everything else (WorkStream,
    # etc.) is appended after them, in whatever order it's found.
    _AUTO_MATCH_FIXED_ORDER = (OBDC.DataContainer, OBDC.FileTree)

    def _auto_matched_requests(self, graph: Graph) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        seen: set = set()
        for subject in graph.subjects(RDF.type, None):
            if not isinstance(subject, URIRef) or subject in seen:
                continue
            seen.add(subject)
            if not self._is_surfaceable(graph, subject):
                continue
            if not self._components.match(graph, subject):
                continue
            requests.append({"data": str(subject), "region": "content"})
        requests.sort(key=lambda request: self._auto_match_priority(graph, request))
        return requests

    def _auto_match_priority(self, graph: Graph, request: Dict[str, Any]) -> int:
        subject = URIRef(str(request["data"]))
        types = set(graph.objects(subject, RDF.type))
        for index, fixed_type in enumerate(self._AUTO_MATCH_FIXED_ORDER):
            if fixed_type in types:
                return index
        return len(self._AUTO_MATCH_FIXED_ORDER)

    def _is_surfaceable(self, graph: Graph, subject: URIRef) -> bool:
        """Auto-match only entities of a class explicitly marked
        obdc:SurfaceableEntity — a Component's required_uris says how to
        render an entity, not whether it should appear unprompted at all.
        """
        return any(
            (entity_type, RDF.type, OBDC.SurfaceableEntity) in graph
            for entity_type in graph.objects(subject, RDF.type)
        )

    def _with_resolved_tile(
        self,
        graph: Graph,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        data_reference = str(
            request.get("data", request.get("data_id", ""))
        ).strip()
        tile_class = str(
            request.get("tileClass", request.get("tile_class", ""))
        ).strip()

        if data_reference:
            matched_components: List[Type[ComponentPort]] = self._components.match(
                graph,
                URIRef(data_reference),
            )
        elif tile_class:
            matched_components = self._components.match_tile_class(tile_class)
        else:
            raise ValueError(
                f"Request must specify either 'data' or 'tileClass': {request}"
            )

        if not matched_components:
            raise ValueError(f"No registered component satisfies request: {request}")

        matched_components.sort(
            key=lambda component: (
                -len(component.METADATA.required_uris),
                component.METADATA.id,
            )
        )
        resolved_component = matched_components[0]
        resolved_request = dict(request)
        resolved_request.pop("tileClass", None)
        resolved_request.pop("tile_class", None)
        resolved_request["tile"] = resolved_component.METADATA.tag
        resolved_request["closed"] = bool(resolved_component.METADATA.default_closed)
        if data_reference:
            self._apply_size_envelope(
                resolved_request,
                resolved_component.METADATA,
                graph,
                URIRef(data_reference),
            )
        return resolved_request

    def _apply_size_envelope(
        self,
        request: Dict[str, Any],
        metadata: ComponentMetadata,
        graph: Graph,
        entity: URIRef,
    ) -> None:
        """Fill in the column/row envelope the Component itself calls for.

        Only fills keys the request didn't already set explicitly, so a
        caller-supplied envelope always wins. `preferredColumns` starts at
        the Component's declared `min_columns` and grows to fit
        `size_property`'s literal length (at `chars_per_column` characters
        per column) when the Component declares both — e.g. a name Tile
        that must not truncate its title — capped at `max_columns` so one
        very long value can't blow out the layout.
        """
        preferred_columns = metadata.min_columns
        if metadata.size_property and metadata.chars_per_column:
            text_length = self._literal_length(graph, entity, metadata.size_property)
            if text_length:
                preferred_columns = max(
                    metadata.min_columns,
                    math.ceil(text_length / metadata.chars_per_column),
                )
        if metadata.max_columns is not None:
            preferred_columns = min(preferred_columns, metadata.max_columns)

        request.setdefault("minColumns", min(metadata.min_columns, preferred_columns))
        request.setdefault("preferredColumns", preferred_columns)
        request.setdefault(
            "maxColumns",
            metadata.max_columns if metadata.max_columns is not None else preferred_columns,
        )
        request.setdefault("minRows", metadata.min_rows)
        request.setdefault("preferredRows", metadata.min_rows)
        request.setdefault(
            "maxRows",
            metadata.max_rows if metadata.max_rows is not None else metadata.min_rows,
        )

    @staticmethod
    def _literal_length(graph: Graph, entity: URIRef, property_uri: str) -> int:
        value: Optional[Any] = graph.value(subject=entity, predicate=URIRef(property_uri))
        return len(str(value)) if value is not None else 0
