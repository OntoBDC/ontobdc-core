import math
import time
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Type, cast

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import ComponentPort
from ontobdc.storage.adapter.bootstrap import StorageNamespaceBootstrap

_OBDC = StorageNamespaceBootstrap.OBDC
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
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


FILE_SIZE_TILE_CLASS_URI = (
    "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#FileSizeTile"
)
FILE_VIEWER_TILE_CLASS_URI = (
    "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#FileViewerTile"
)

#region debug-point (infobim-view-slow-crash): H4 instrumentation output
_DBG_AUTO_MATCH: Dict[str, Any] = {}
_DBG_RESOLVE_TILE: Dict[str, Any] = {
    "count": 0,
    "seconds": 0.0,
    "seconds_size_envelope": 0.0,
}
#endregion


class SurfaceMatchedCapability(TransformationCapability):
    """Match presentation requests to registered Components."""

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_matched",
        version="1.0.0",
        name="Surface Matched",
        description="Match presentation data to compatible Component definitions and support envelopes.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "component", "matching", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Presentation data was matched to compatible Component "
                    "definitions and support envelopes."
                ),
            },
            "debug_entry": {
                "en": (
                    "Matching presentation data against compatible Component "
                    "definitions and support envelopes."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()
        self._components = ComponentLoader()
        self._context_adapter = SurfaceContextAdapter()
        # Instance-level caches for H4 (one cache per capability run) — rdflib Graph
        # identity is not stable across interpreter runs, so per-instance dicts are safer
        # than module-level LRU and still provide ~10x speedup on large graphs.
        self._is_surfaceable_cache: Dict[URIRef, bool] = {}
        self._subject_types_cache: Dict[URIRef, FrozenSet[URIRef]] = {}
        self._surfaceable_types_cache: Dict[URIRef, bool] = {}
        self._match_cache: Dict[URIRef, List[Type[ComponentPort]]] = {}

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_matched)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        #region debug-point (infobim-view-slow-crash): reset counters before run
        global _DBG_AUTO_MATCH, _DBG_RESOLVE_TILE
        _DBG_AUTO_MATCH = {}
        _DBG_RESOLVE_TILE = {
            "count": 0,
            "seconds": 0.0,
            "seconds_size_envelope": 0.0,
        }
        _dbg_t_execute: float = time.perf_counter()
        #endregion
        # Clear per-run caches (they key on graph URIs so they're not safe between
        # graph instances — cheap to rebuild once per capability).
        self._is_surfaceable_cache.clear()
        self._subject_types_cache.clear()
        self._surfaceable_types_cache.clear()
        self._match_cache.clear()

        graph = self._gathered_graph(context)
        explicit_requests = self._context_adapter.surface_matches(context)
        requests = explicit_requests or self._default_requests(graph)
        is_explicit = explicit_requests is not None and len(explicit_requests) > 0
        resolved_requests: List[Dict[str, Any]] = []
        for request in requests:
            #region debug-point (infobim-view-slow-crash): H4 resolve tile instrumentation
            _dbg_rt0: float = time.perf_counter()
            _DBG_RESOLVE_TILE["count"] += 1
            #endregion
            resolved = self._with_resolved_tile(graph, request, strict=is_explicit)
            #region debug-point (infobim-view-slow-crash): H4 resolve tile timer
            _DBG_RESOLVE_TILE["seconds"] += time.perf_counter() - _dbg_rt0
            #endregion
            if resolved is not None:
                resolved_requests.append(resolved)
        matches = normalize_matches(resolved_requests)

        document = upsert_json_script(self._surface.read(context), MATCHES_ID, matches)
        document = set_state_marker(document, "surface_matched")
        path = self._surface.write(context, document)
        self._surface.require_check(context, check_surface_matched, "surface_matched")

        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_MATCHED,
            "surface_path": str(path),
            "match_count": len(matches),
            #region debug-point (infobim-view-slow-crash): inject H4 evidence
            "_dbg_seconds_total": round(time.perf_counter() - _dbg_t_execute, 4),
            "_dbg_requests_total": len(requests),
            "_dbg_requests_explicit": is_explicit,
            "_dbg_auto_match": _DBG_AUTO_MATCH,
            "_dbg_resolve_tile": {
                "count": _DBG_RESOLVE_TILE["count"],
                "seconds": round(_DBG_RESOLVE_TILE["seconds"], 4),
            },
            #endregion
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _gathered_graph(self, context: CliContextPort) -> Graph:
        path = DataGatheredCapability.state_path(context)
        graph = Graph()
        graph.parse(str(path), format="json-ld")
        return graph

    _AUTO_MATCH_FIXED_ORDER = (_OBDC.DataContainer, _OBDC.FileTree)

    def _default_requests(self, graph: Graph) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = self._auto_matched_requests(graph)
        if self._components.match_tile_class(FILE_SIZE_TILE_CLASS_URI):
            requests.append(
                {"tileClass": FILE_SIZE_TILE_CLASS_URI, "region": "content"}
            )
        if self._components.match_tile_class(FILE_VIEWER_TILE_CLASS_URI):
            requests.append(
                {"tileClass": FILE_VIEWER_TILE_CLASS_URI, "region": "content"}
            )
        return requests

    def _auto_matched_requests(self, graph: Graph) -> List[Dict[str, Any]]:
        requests: List[Dict[str, Any]] = []
        seen: set = set()
        #region debug-point (infobim-view-slow-crash): H4 O(N·C) instrumentation
        global _DBG_AUTO_MATCH
        _dbg_t0: float = time.perf_counter()
        _dbg_subjects_total: int = 0
        _dbg_subjects_surfaceable: int = 0
        _dbg_surfaceable_seconds: float = 0.0
        _dbg_match_seconds: float = 0.0
        _dbg_match_cache_hits: int = 0
        _dbg_match_cache_misses: int = 0
        #endregion
        for subject in graph.subjects(RDF.type, None):
            if not isinstance(subject, URIRef) or subject in seen:
                continue
            seen.add(subject)
            #region debug-point (infobim-view-slow-crash): H4 counters
            _dbg_subjects_total += 1
            _dbgs1: float = time.perf_counter()
            #endregion
            if not self._is_surfaceable(graph, subject):
                continue
            #region debug-point (infobim-view-slow-crash): H4 counters
            _dbgs2: float = time.perf_counter()
            _dbg_surfaceable_seconds += _dbgs2 - _dbgs1
            _dbg_subjects_surfaceable += 1
            #endregion
            # H4 cache: previously _auto_matched_requests runs match() once,
            # _with_resolved_tile then runs match() AGAIN for the same subject
            # when request is a "data"-style request (most of them). Cache the
            # match result list by subject URI so we're O(C·graph traversal instead of O(2·N·C).
            cached_matches: Optional[List[Type[ComponentPort]]] = self._match_cache.get(subject)
            if cached_matches is not None:
                _dbg_match_cache_hits += 1
                if not cached_matches:
                    continue
            else:
                _dbg_match_cache_misses += 1
                matched: List[Type[ComponentPort]] = self._components.match(graph, subject)
                self._match_cache[subject] = matched
                if not matched:
                    continue
                # H4 timer path (just elapsed).
            #region debug-point (infobim-view-slow-crash): H4 counters
            _dbgs3: float = time.perf_counter()
            _dbg_match_seconds += _dbgs3 - _dbgs2
            #endregion
            requests.append({"data": str(subject), "region": "content"})
        requests.sort(key=lambda request: self._auto_match_priority(graph, request))
        #region debug-point (infobim-view-slow-crash): persist H4 metrics for caller
        _DBG_AUTO_MATCH = {
            "seconds_total": round(time.perf_counter() - _dbg_t0, 4),
            "subjects_total": _dbg_subjects_total,
            "subjects_surfaceable": _dbg_subjects_surfaceable,
            "requests_matched": len(requests),
            "seconds_surfaceable_check": round(_dbg_surfaceable_seconds, 4),
            "seconds_component_match": round(_dbg_match_seconds, 4),
            "match_cache_hits": _dbg_match_cache_hits,
            "match_cache_misses": _dbg_match_cache_misses,
        }
        #endregion
        return requests

    def _auto_match_priority(self, graph: Graph, request: Dict[str, Any]) -> int:
        subject = URIRef(str(request["data"]))
        types = self._cached_subject_types(graph, subject)
        for index, fixed_type in enumerate(self._AUTO_MATCH_FIXED_ORDER):
            if fixed_type in types:
                return index
        return len(self._AUTO_MATCH_FIXED_ORDER)

    def _cached_subject_types(self, graph: Graph, subject: URIRef) -> FrozenSet[URIRef]:
        cached = self._subject_types_cache.get(subject)
        if cached is not None:
            return cached
        types = frozenset(
            uri for uri in graph.objects(subject, RDF.type) if isinstance(uri, URIRef)
        )
        self._subject_types_cache[subject] = types
        return types

    def _cached_type_is_surfaceable(self, graph: Graph, entity_type: URIRef) -> bool:
        cached = self._surfaceable_types_cache.get(entity_type)
        if cached is not None:
            return cached
        # H4 cache type-level surfaceability — exact same semantics as the original
        # single-graph-triple check; cached per RDF type so it's evaluated once
        # per type instead of once per subject of that type (1000x same WorkStream
        # or File type would otherwise pay the same triple-matching cost).
        result: bool = (entity_type, RDF.type, _OBDC.SurfaceableEntity) in graph
        self._surfaceable_types_cache[entity_type] = result
        return result

    def _is_surfaceable(self, graph: Graph, subject: URIRef) -> bool:
        cached = self._is_surfaceable_cache.get(subject)
        if cached is not None:
            return cached
        result: bool = any(
            self._cached_type_is_surfaceable(graph, entity_type)
            for entity_type in self._cached_subject_types(graph, subject)
        )
        self._is_surfaceable_cache[subject] = result
        return result

    def _with_resolved_tile(
        self,
        graph: Graph,
        request: Dict[str, Any],
        *,
        strict: bool = True,
    ) -> Optional[Dict[str, Any]]:
        data_reference = str(
            request.get("data", request.get("data_id", ""))
        ).strip()
        tile_class = str(
            request.get("tileClass", request.get("tile_class", ""))
        ).strip()

        if data_reference:
            subject_ref = URIRef(data_reference)
            cached_matches = self._match_cache.get(subject_ref)
            if cached_matches is not None:
                matched_components: List[Type[ComponentPort]] = list(cached_matches)
            else:
                matched_components = self._components.match(graph, subject_ref)
                self._match_cache[subject_ref] = list(matched_components)
        elif tile_class:
            matched_components = self._components.match_tile_class(tile_class)
        else:
            raise ValueError(
                f"Request must specify either 'data' or 'tileClass': {request}"
            )

        # `-terminal`-tagged Components (e.g. TerminalLogoTile) exist only to
        # satisfy TerminalSurfaceRenderer's own separate resolver
        # (adapter/terminal/surface_renderer.py) for the same view:*Tile
        # ontology class — the HTML Surface this capability writes has no
        # custom element registered under that tag. Same exclusion
        # `ontobdc_view.component.adapter.surface.render.SurfaceResolutionService
        # .resolve_placement_tag` already applies when resolving tags for the
        # embedded `defaultSurfaceLayouts` payload.
        html_components = [
            component
            for component in matched_components
            if not str(component.METADATA.tag).endswith("-terminal")
        ]
        matched_components = html_components or matched_components

        if not matched_components:
            if strict:
                raise ValueError(
                    f"No registered component satisfies request: {request}"
                )
            if data_reference:
                raise ValueError(
                    f"No registered component satisfies data request: {request}"
                )
            return None

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
        else:
            self._apply_static_size_envelope(
                resolved_request,
                resolved_component.METADATA,
            )

        resolved_region = str(
            resolved_request.get("region", "content")
        ).strip().lower()
        if resolved_region in {"operation", "pinned"}:
            resolved_request["minRows"] = 1
            resolved_request["preferredRows"] = 1
            resolved_request["maxRows"] = 1

        return resolved_request

    def _apply_size_envelope(
        self,
        request: Dict[str, Any],
        metadata: ComponentMetadata,
        graph: Graph,
        entity: URIRef,
    ) -> None:
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
    def _apply_static_size_envelope(
        request: Dict[str, Any], metadata: ComponentMetadata
    ) -> None:
        request.setdefault("minColumns", metadata.min_columns)
        request.setdefault("preferredColumns", metadata.min_columns)
        request.setdefault(
            "maxColumns",
            metadata.max_columns if metadata.max_columns is not None else metadata.min_columns,
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
