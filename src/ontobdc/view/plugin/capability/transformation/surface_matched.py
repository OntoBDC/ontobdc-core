import math
from typing import Any, Dict, List, Optional, Tuple, Type, cast

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

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_MATCHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_matched)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        graph = self._gathered_graph(context)
        explicit_requests = self._context_adapter.surface_matches(context)
        requests = explicit_requests or self._default_requests(graph)
        is_explicit = explicit_requests is not None and len(explicit_requests) > 0
        resolved_requests: List[Dict[str, Any]] = []
        for request in requests:
            resolved = self._with_resolved_tile(graph, request, strict=is_explicit)
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
        return requests

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
        return any(
            (entity_type, RDF.type, _OBDC.SurfaceableEntity) in graph
            for entity_type in graph.objects(subject, RDF.type)
        )

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
