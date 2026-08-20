import time
from pathlib import Path
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

#region debug-point (infobim-view-slow-crash): H2 instrumentation metrics import
from ontobdc.view.plugin.check import surface_common as _dbg_sc
#endregion


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
        #region debug-point (infobim-view-slow-crash): H2 instrumentation (131s step)
        _dbg_t0: float = time.perf_counter()
        #endregion
        document = self._surface.read(context)
        #region debug-point (infobim-view-slow-crash): read timer
        _dbg_t_read: float = time.perf_counter()
        _dbg_ctx_t0: float = time.perf_counter()
        #endregion
        scripts = self._context_adapter.component_scripts(context)
        #region debug-point (infobim-view-slow-crash): context adapter timer
        _dbg_t_ctx: float = time.perf_counter()
        _dbg_src_t0: float = time.perf_counter()
        #endregion
        if not scripts:
            scripts = self._read_component_sources(document, context)
        #region debug-point (infobim-view-slow-crash): read sources timer
        _dbg_t_src: float = time.perf_counter()
        #endregion
        if not scripts:
            raise ValueError(
                "No complete build-ready Surface component set was available. "
                "Install ontobdc-view with build-ready components or provide "
                "surface_component_scripts."
            )

        #region debug-point (infobim-view-slow-crash): embed timer
        _dbg_emb_t0: float = time.perf_counter()
        #endregion
        document = embed_component_scripts(document, scripts)
        #region debug-point (infobim-view-slow-crash): embed done, state marker
        _dbg_t_embed: float = time.perf_counter()
        _dbg_state_t0: float = time.perf_counter()
        #endregion
        document = set_state_marker(document, "surface_packaged")
        #region debug-point (infobim-view-slow-crash): state done, write
        _dbg_t_state: float = time.perf_counter()
        _dbg_write_t0: float = time.perf_counter()
        #endregion
        path = self._surface.write(context, document)
        self._write_file_viewer(path.parent)
        #region debug-point (infobim-view-slow-crash): write done, check
        _dbg_t_write: float = time.perf_counter()
        _dbg_check_t0: float = time.perf_counter()
        #endregion
        self._surface.require_check(context, check_surface_packaged, "surface_packaged")
        #region debug-point (infobim-view-slow-crash): check done, snapshot metrics
        _dbg_t_check: float = time.perf_counter()
        _dbg_common = dict(getattr(_dbg_sc, "_DBG_METRICS", {}) or {})
        #endregion
        return {
            "resulting_state": SurfaceGenerationProcessState.SURFACE_PACKAGED,
            "surface_path": str(path),
            "component_script_count": len(scripts),
            #region debug-point (infobim-view-slow-crash): inject H2 evidence
            "_dbg_seconds_total": round(_dbg_t_check - _dbg_t0, 4),
            "_dbg_document_chars": len(document),
            "_dbg_seconds_read": round(_dbg_t_read - _dbg_t0, 4),
            "_dbg_seconds_context_scripts": round(_dbg_t_ctx - _dbg_ctx_t0, 4),
            "_dbg_seconds_read_component_sources": round(_dbg_t_src - _dbg_src_t0, 4),
            "_dbg_seconds_embed_scripts": round(_dbg_t_embed - _dbg_emb_t0, 4),
            "_dbg_seconds_set_state": round(_dbg_t_state - _dbg_state_t0, 4),
            "_dbg_seconds_write": round(_dbg_t_write - _dbg_write_t0, 4),
            "_dbg_seconds_require_check": round(_dbg_t_check - _dbg_check_t0, 4),
            "_dbg_check_common_metrics": _dbg_common,
            #endregion
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

    def _write_file_viewer(self, container_path: Path) -> None:
        """Write the standalone file-viewer page inside the OntoBDC marker dir.

        `onto-file-tree-tile` opens this page
        (`.__ontobdc__/onto-file-viewer.html`, relative to the container
        root) with the clicked file's path passed by reference in the
        query string — the only place, and only moment, a real
        container file is ever read. Keeping it inside the already-ignored
        `.__ontobdc__` directory guarantees it never appears as an
        ordinary user-visible container file in the RO-Crate inventory or
        the file tree tile. Missing `ontobdc_view` (or its viewer
        asset) is non-fatal here the same way missing component
        scripts already are handled by the caller: the Surface itself
        still renders, just without the ability to open a file's content.
        """
        try:
            import ontobdc_view
        except Exception:
            return

        try:
            source = ontobdc_view.file_viewer_source()
        except Exception:
            return
        if not isinstance(source, str) or not source.strip():
            return

        marker_dir: Path = container_path / ".__ontobdc__"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "onto-file-viewer.html").write_text(
            source, encoding="utf-8"
        )

    def _read_component_sources(self, document: str, context: CliContextPort) -> List[str]:
        try:
            import ontobdc_view
        except Exception:
            return []

        try:
            root_path = context.root_path
        except Exception:
            root_path = None

        scripts: List[str] = []
        for tag in self._required_component_tags(document):
            try:
                source = ontobdc_view.component_source(tag, root_path=root_path)
            except Exception:
                return []
            if not isinstance(source, str) or not source.strip():
                return []
            scripts.append(source)
        return scripts
