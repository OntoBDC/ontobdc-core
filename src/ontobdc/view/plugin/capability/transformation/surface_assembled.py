import re
import time
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.view.adapter.surface.document import (
    MATCHES_ID,
    assemble_surface_markup,
    extract_json_script,
    set_state_marker,
)
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.plugin.check.is_surface_assembled.check import main as check_surface_assembled

#region debug-point (infobim-view-slow-crash): import surface_common metrics
from ontobdc.view.plugin.check import surface_common as _dbg_sc
#endregion


class SurfaceAssembledCapability(TransformationCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.view.plugin.capability.transformation.target.surface_assembled",
        version="1.0.0",
        name="Surface Assembled",
        description="Compose operation, content and pinned regions with matched Tiles and runtime layout constraints.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "assembly", "transformation"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Surface presentation tiles were assembled into their final "
                    "viewport layout ready for packaging and rendering."
                ),
            },
            "debug_entry": {
                "en": (
                    "Assembling Surface presentation tiles into the final "
                    "viewport layout."
                ),
            },
        },
    )

    def __init__(self) -> None:
        self._surface = SurfaceTransformationAdapter()

    def label(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ASSEMBLED.label(lang)

    def description(self, lang: str = "en") -> str:
        return SurfaceGenerationProcessState.SURFACE_ASSEMBLED.description(lang)

    def check(self, context: CliContextPort) -> bool:
        return self._surface.check(context, check_surface_assembled)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        #region debug-point (infobim-view-slow-crash): H3 instrumentation (59s step)
        _dbg_t0: float = time.perf_counter()
        #endregion
        document = self._surface.read(context)
        #region debug-point (infobim-view-slow-crash): read timer
        _dbg_t_read: float = time.perf_counter()
        #endregion
        matches = extract_json_script(document, MATCHES_ID)
        if not isinstance(matches, list):
            raise ValueError("Surface matches are missing or invalid")
        #region debug-point (infobim-view-slow-crash): extract matches timer
        _dbg_t_extract: float = time.perf_counter()
        _dbg_markup_t0: float = time.perf_counter()
        #endregion
        document = assemble_surface_markup(document, matches)
        #region debug-point (infobim-view-slow-crash): markup timer
        _dbg_t_markup: float = time.perf_counter()
        _dbg_regex_t0: float = time.perf_counter()
        #endregion
        document = re.sub(
            r"<onto-presentation-surface\b(?![^>]*\bdata-ontobdc-assembled=)",
            '<onto-presentation-surface data-ontobdc-assembled="true"',
            document,
            flags=re.IGNORECASE,
        )
        #region debug-point (infobim-view-slow-crash): regex sub timer
        _dbg_t_regex: float = time.perf_counter()
        _dbg_state_t0: float = time.perf_counter()
        #endregion
        document = set_state_marker(document, "surface_assembled")
        #region debug-point (infobim-view-slow-crash): state marker timer
        _dbg_t_state: float = time.perf_counter()
        _dbg_write_t0: float = time.perf_counter()
        #endregion
        path = self._surface.write(context, document)
        #region debug-point (infobim-view-slow-crash): write timer
        _dbg_t_write: float = time.perf_counter()
        _dbg_check_t0: float = time.perf_counter()
        #endregion
        self._surface.require_check(context, check_surface_assembled, "surface_assembled")
        #region debug-point (infobim-view-slow-crash): check timer & common metrics snapshot
        _dbg_t_check: float = time.perf_counter()
        _dbg_common = dict(getattr(_dbg_sc, "_DBG_METRICS", {}) or {})
        #endregion
        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_ASSEMBLED,
            "surface_path": str(path),
            "tile_count": len(matches),
            #region debug-point (infobim-view-slow-crash): inject H3 evidence
            "_dbg_seconds_total": round(_dbg_t_check - _dbg_t0, 4),
            "_dbg_document_chars": len(document),
            "_dbg_seconds_read": round(_dbg_t_read - _dbg_t0, 4),
            "_dbg_seconds_extract_matches": round(_dbg_t_extract - _dbg_t_read, 4),
            "_dbg_seconds_assemble_markup": round(_dbg_t_markup - _dbg_markup_t0, 4),
            "_dbg_seconds_regex_assembled_attr": round(_dbg_t_regex - _dbg_regex_t0, 4),
            "_dbg_seconds_set_state": round(_dbg_t_state - _dbg_state_t0, 4),
            "_dbg_seconds_write": round(_dbg_t_write - _dbg_write_t0, 4),
            "_dbg_seconds_require_check": round(_dbg_t_check - _dbg_check_t0, 4),
            "_dbg_check_common_metrics": _dbg_common,
            #endregion
        }

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)
