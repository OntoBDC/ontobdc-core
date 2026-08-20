import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import JSONLD_ID, extract_json_script, set_state_marker
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.adapter.work_stream_script_machine import (
    WorkStreamScriptGenerationStateTransitionHandler,
)
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_entity_views_published.check import (
    main as check_entity_views_published,
)

_WORK_STREAM_PATH_SEGMENT = "work_stream"


def _atomic_write_text(path: Path, content: str, *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            # fsync(2) forces the OS to flush page cache to the underlying
            # storage device — necessary for true power-loss durability, but
            # for build pipelines (N standalone detail pages) it means a
            # per-file synchronous round-trip through the storage filter
            # driver. On OneDrive / SMB / DFS this round-trip is ~100-300ms
            # and dominates the whole step (~200 s for 1000 files). For a
            # pipeline artifact a crash-safe "best effort" replace is enough;
            # keep durable mode as an explicit opt-in.
            if durable:
                os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


class EntityViewsPublishedCapability(TransformationCapability):
    """Publish a standalone detail page for every entity `ontobdc_view` has
    a Page renderer for.

    Mostly thin orchestration: this capability enumerates entities from the
    already-resolved Surface JSON-LD and delegates rendering (and the
    decision of whether an entity type has a page at all) entirely to
    `ontobdc_view.render_entity_view`. It has no HTML/Jinja logic and no
    separate staleness check — every run regenerates every matched page
    fresh, the same way `index.html` itself has no incremental repair
    step, just full regeneration.

    One exception to "no per-entity-type knowledge": once at least one
    WorkStream page is published, this also drives
    `WorkStreamScriptGenerationProcessState` to (re)write that page's split
    runtime JS under `.__ontobdc__/asset/work_stream_view/` — those
    `<script src>` tags are useless without it, and nothing else in the
    pipeline currently triggers that statechart. A failure there is
    reported back (`work_stream_scripts_error`) but never raised, so a
    broken WorkStream runtime script never blocks every other entity's
    page from publishing.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.entity_views_published",
        version="1.0.0",
        name="Entity Views Published",
        description=(
            "Publish a standalone detail page for every entity ontobdc_view "
            "has a Page renderer for."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "html", "page", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Standalone detail pages were published for every entity "
                    "supported by an available Page renderer."
                ),
            },
            "debug_entry": {
                "en": (
                    "Publishing standalone detail pages for every entity "
                    "supported by an available Page renderer."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_entity_views_published)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        try:
            import ontobdc_view
        except ImportError:
            document = self._surface.read(context)
            document = set_state_marker(document, "entity_views_published")
            self._surface.write(context, document)
            return {
                "resulting_state": SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED,
                "published_view_count": 0,
                "work_stream_scripts_generated": [],
                "work_stream_scripts_error": "",
            }

        #region debug-point (infobim-view-slow-crash): H1 instrumentation (201s step)
        _dbg_t0: float = time.perf_counter()
        #endregion
        document = self._surface.read(context)
        #region debug-point (infobim-view-slow-crash): read timer
        _dbg_t_read: float = time.perf_counter()
        #endregion
        container_path = self._surface.path(context).parent
        nodes = self._entity_nodes(document)

        published: List[str] = []
        work_stream_page_published: bool = False
        #region debug-point (infobim-view-slow-crash): H1 detailed loop instrumentation
        _dbg_loop_total: int = 0
        _dbg_skipped_render: int = 0
        _dbg_skipped_result: int = 0
        _dbg_render_seconds: float = 0.0
        _dbg_write_seconds: float = 0.0
        #endregion
        for node in nodes:
            #region debug-point (infobim-view-slow-crash): H1 per-iteration counters
            _dbg_loop_total += 1
            _dbg_r0: float = time.perf_counter()
            #endregion
            result = ontobdc_view.render_entity_view(
                self._type_uris(node), node, graph_nodes=nodes
            )
            #region debug-point (infobim-view-slow-crash): H1 per-iteration timer
            _dbg_r1: float = time.perf_counter()
            _dbg_render_seconds += _dbg_r1 - _dbg_r0
            #endregion
            if result is None:
                #region debug-point (infobim-view-slow-crash): H1 skip counter
                _dbg_skipped_render += 1
                #endregion
                continue
            identifier = str(result.get("identifier") or "").strip()
            path_segment = str(result.get("path_segment") or "").strip()
            html = result.get("html")
            if not identifier or not path_segment or not isinstance(html, str):
                #region debug-point (infobim-view-slow-crash): H1 invalid skip counter
                _dbg_skipped_result += 1
                #endregion
                continue
            target_path = (
                container_path / ".__ontobdc__" / "view" / path_segment / f"{identifier}.html"
            )
            #region debug-point (infobim-view-slow-crash): H1 write timer (includes fsync)
            _dbg_w0: float = time.perf_counter()
            #endregion
            _atomic_write_text(target_path, html)
            #region debug-point (infobim-view-slow-crash): H1 write timer stop
            _dbg_write_seconds += time.perf_counter() - _dbg_w0
            #endregion
            published.append(str(target_path))
            if path_segment == _WORK_STREAM_PATH_SEGMENT:
                work_stream_page_published = True

        work_stream_scripts_generated: List[str] = []
        work_stream_scripts_error: str = ""
        if work_stream_page_published:
            try:
                script_response = WorkStreamScriptGenerationStateTransitionHandler(
                    context
                ).execute()
                work_stream_scripts_generated = list(
                    script_response.content.get("visited_states", [])
                )
            except Exception as exc:  # noqa: BLE001 - see docstring: never blocks other pages
                work_stream_scripts_error = str(exc)

        #region debug-point (infobim-view-slow-crash): H1 after-loop timers
        _dbg_t_loop_done: float = time.perf_counter()
        #endregion
        document = set_state_marker(document, "entity_views_published")
        #region debug-point (infobim-view-slow-crash): state marker timer
        _dbg_t_state: float = time.perf_counter()
        #endregion
        self._surface.write(context, document)
        #region debug-point (infobim-view-slow-crash): final write timer
        _dbg_t_write: float = time.perf_counter()
        #endregion

        return {
            "resulting_state": SurfaceGenerationProcessState.ENTITY_VIEWS_PUBLISHED,
            "published_view_count": len(published),
            "published_view_paths": published,
            "work_stream_scripts_generated": work_stream_scripts_generated,
            "work_stream_scripts_error": work_stream_scripts_error,
            #region debug-point (infobim-view-slow-crash): inject H1 evidence
            "_dbg_seconds_total": round(_dbg_t_write - _dbg_t0, 4),
            "_dbg_total_nodes": _dbg_loop_total,
            "_dbg_document_chars": len(document),
            "_dbg_seconds_read": round(_dbg_t_read - _dbg_t0, 4),
            "_dbg_seconds_loop": round(_dbg_t_loop_done - _dbg_t_read, 4),
            "_dbg_seconds_set_state": round(_dbg_t_state - _dbg_t_loop_done, 4),
            "_dbg_seconds_final_write": round(_dbg_t_write - _dbg_t_state, 4),
            "_dbg_render_seconds_total": round(_dbg_render_seconds, 4),
            "_dbg_write_seconds_total": round(_dbg_write_seconds, 4),
            "_dbg_average_render_ms": round(
                1000 * (_dbg_render_seconds / _dbg_loop_total), 2
            ) if _dbg_loop_total else 0.0,
            "_dbg_average_write_ms": round(
                1000 * (_dbg_write_seconds / len(published)), 2
            ) if published else 0.0,
            "_dbg_skipped_render_none": _dbg_skipped_render,
            "_dbg_skipped_result_invalid": _dbg_skipped_result,
            #endregion
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def _entity_nodes(self, document: str) -> List[Dict[str, Any]]:
        try:
            graph = extract_json_script(document, JSONLD_ID)
        except (ValueError, json.JSONDecodeError):
            return []
        if isinstance(graph, dict):
            return [graph]
        if isinstance(graph, list):
            return [node for node in graph if isinstance(node, dict)]
        return []

    def _type_uris(self, node: Dict[str, Any]) -> List[str]:
        raw_type = node.get("@type")
        if isinstance(raw_type, str):
            return [raw_type]
        if isinstance(raw_type, list):
            return [str(item) for item in raw_type]
        return []
