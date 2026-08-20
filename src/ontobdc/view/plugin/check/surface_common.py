import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

_LOGGER: logging.Logger = logging.getLogger(__name__)

from ontobdc.view.adapter.surface.document import (
    CONFIG_ID,
    DEFAULT_LAYOUTS_ID,
    JSONLD_ID,
    MATCHES_ID,
    SURFACE_TAG,
    contains_external_runtime_reference,
    extract_json_script,
    get_state_marker,
    read_surface,
    resolve_surface_path,
)
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState


#region debug-point (infobim-view-slow-crash): H2/H3 instrumentation
_DBG_METRICS: Dict[str, Any] = {}
#endregion


_STATE_NAME_TO_STATE = {
    state.value.strip("_"): state for state in SurfaceGenerationProcessState
}


def resolve_document(surface_path: Optional[str]) -> tuple[Path, str]:
    path = resolve_surface_path(surface_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path, read_surface(path)


def state_reached(document: str, target: SurfaceGenerationProcessState) -> bool:
    marker = get_state_marker(document)
    if not marker:
        return False
    current = _STATE_NAME_TO_STATE.get(marker)
    if current is None:
        return False
    states = list(SurfaceGenerationProcessState)
    return states.index(current) >= states.index(target)


def has_initialized_surface(document: str) -> bool:
    return (
        "<!doctype html" in document.lower()
        and re.search(r"<html\b", document, re.IGNORECASE) is not None
        and re.search(r"<head\b", document, re.IGNORECASE) is not None
        and re.search(r"<body\b", document, re.IGNORECASE) is not None
        and re.search(rf"<{SURFACE_TAG}\b", document, re.IGNORECASE) is not None
    )


def has_jsonld(document: str) -> bool:
    try:
        payload = extract_json_script(document, JSONLD_ID)
    except (ValueError, json.JSONDecodeError):
        return False
    return isinstance(payload, (dict, list))


def has_surface_config(document: str) -> bool:
    try:
        config = extract_json_script(document, CONFIG_ID)
    except (ValueError, json.JSONDecodeError):
        return False
    if not isinstance(config, dict):
        return False
    content = config.get("content")
    if not isinstance(content, dict) or content.get("mode") not in {"fixed", "scroll"}:
        return False
    return all(
        key in config
        for key in ("operation", "pinned", "slotTarget", "gap", "padding", "tileMargin")
    )


def has_surface_matches(document: str) -> bool:
    try:
        matches = extract_json_script(document, MATCHES_ID)
    except (ValueError, json.JSONDecodeError):
        return False
    if not isinstance(matches, list):
        return False

    required = {
        "tile",
        "region",
        "minColumns",
        "preferredColumns",
        "maxColumns",
        "minRows",
        "preferredRows",
        "maxRows",
    }
    for item in matches:
        if not isinstance(item, dict) or not required.issubset(item):
            return False
    return True


def has_valid_default_layouts(document: str) -> bool:
    try:
        payload = extract_json_script(document, DEFAULT_LAYOUTS_ID)
    except (ValueError, json.JSONDecodeError):
        # Absence is fine — SURFACE_OPERATIONAL_MATCHED is a legal no-op
        # when no DefaultSurfaceLayout/PresentationSurface RDF is configured.
        return True
    return isinstance(payload, list) and all(
        isinstance(item, dict) and "iri" in item for item in payload
    )


def has_assembled_tiles(document: str) -> bool:
    #region debug-point (infobim-view-slow-crash): H2/H3 instrumentation for O(T·html_bytes)
    global _DBG_METRICS
    _dbg_t0: float = time.perf_counter()
    #endregion
    if re.search(
        rf"<{SURFACE_TAG}\b[^>]*\bdata-ontobdc-assembled=[\"']true[\"']",
        document,
        re.IGNORECASE,
    ) is None:
        #region debug-point (infobim-view-slow-crash): persist short-circuit metric
        _DBG_METRICS["has_assembled_tiles"] = {
            "seconds": round(time.perf_counter() - _dbg_t0, 4),
            "matches": 0,
            "document_chars": len(document),
            "short_circuit_assembled_attr": True,
            "per_tile_regex_searches": 0,
        }
        #endregion
        return False

    try:
        matches = extract_json_script(document, MATCHES_ID)
    except (ValueError, json.JSONDecodeError):
        #region debug-point (infobim-view-slow-crash): persist error metric
        _DBG_METRICS["has_assembled_tiles"] = {
            "seconds": round(time.perf_counter() - _dbg_t0, 4),
            "matches": 0,
            "document_chars": len(document),
            "matches_invalid": True,
            "per_tile_regex_searches": 0,
        }
        #endregion
        return False
    if not isinstance(matches, list):
        #region debug-point (infobim-view-slow-crash): persist invalid metric
        _DBG_METRICS["has_assembled_tiles"] = {
            "seconds": round(time.perf_counter() - _dbg_t0, 4),
            "matches": 0,
            "document_chars": len(document),
            "matches_not_a_list": True,
            "per_tile_regex_searches": 0,
        }
        #endregion
        return False

    #region debug-point (infobim-view-slow-crash): H2/H3 instrumentation
    _dbg_regex_searches: int = 0
    #endregion

    # Build the expected tile tag attribute lookup ONCE (single pass O(chars))
    # either over the extracted surface inner markup (~50-200 KB) or the full
    # document (~10 MB). Either way it's a SINGLE constant-factor string scan
    # that replaces the previous O(T · len(document)) regex cascade that was
    # reading 40+ GB of string bytes (2 per tile × 2000 tiles × 10 MB) on
    # every check/validate call, causing 5+ minute hangs when the document
    # wasn't freshly assembled or had an unusual surface-open tag ordering.
    #
    # CRITICAL: we MUST NOT fall back to O(T · N_bytes) per-tile regex. That
    # legacy path is the root cause of the 5-minute SurfaceAssembled stall
    # (10 require_check retries × 30s each). A single 10 MB regex scan is
    # always preferable and stays under 1 second even on slow systems.
    surface_body: Optional[str] = _extract_surface_inner_markup(document)
    lut_source: str = surface_body if surface_body is not None else document
    present_tiles: Dict[tuple[str, str], Set[str]] = _build_tile_lut(lut_source) or {}
    _lut_from_full_doc: bool = surface_body is None

    for item in matches:
        if not isinstance(item, dict):
            _DBG_METRICS["has_assembled_tiles"] = {
                "seconds": round(time.perf_counter() - _dbg_t0, 4),
                "matches": len(matches),
                "document_chars": len(document),
                "item_invalid": True,
                "per_tile_regex_searches": _dbg_regex_searches,
                "fast_lut": True,
                "lut_from_full_document": _lut_from_full_doc,
            }
            return False
        tile_name = str(item.get("tile", "")).strip()
        region = str(item.get("region", "")).strip()
        if not tile_name or not region:
            _DBG_METRICS["has_assembled_tiles"] = {
                "seconds": round(time.perf_counter() - _dbg_t0, 4),
                "matches": len(matches),
                "document_chars": len(document),
                "item_missing_fields": True,
                "per_tile_regex_searches": _dbg_regex_searches,
                "fast_lut": True,
                "lut_from_full_document": _lut_from_full_doc,
            }
            return False

        bucket: Optional[Set[str]] = present_tiles.get((tile_name.lower(), region.lower()))
        if bucket is None:
            lut_keys: list[tuple[str, str]] = list(present_tiles.keys())[:20]
            _LOGGER.error(
                "has_assembled_tiles FAIL: tile %r region %r (key=%r) not in LUT "
                "(lut_size=%d sample_keys=%s lut_from_full_doc=%s)",
                tile_name, region, (tile_name.lower(), region.lower()),
                len(present_tiles), lut_keys, _lut_from_full_doc,
            )
            _DBG_METRICS["has_assembled_tiles"] = {
                "seconds": round(time.perf_counter() - _dbg_t0, 4),
                "matches": len(matches),
                "document_chars": len(document),
                "tile_not_found": tile_name,
                "tile_region": region,
                "per_tile_regex_searches": _dbg_regex_searches,
                "fast_lut": True,
                "lut_from_full_document": _lut_from_full_doc,
                "lut_size": len(present_tiles),
                "lut_sample_keys": lut_keys,
            }
            return False
        _dbg_regex_searches += 1

        expected_data: str = str(item.get("data", "")).strip()
        if expected_data and expected_data not in bucket:
            sample_bucket: list[str] = sorted(bucket)[:10]
            _LOGGER.error(
                "has_assembled_tiles FAIL: tile %r region %r resource MISMATCH "
                "expected=%r bucket_size=%d bucket_sample=%s lut_from_full_doc=%s",
                tile_name, region, expected_data[:120],
                len(bucket), sample_bucket, _lut_from_full_doc,
            )
            _DBG_METRICS["has_assembled_tiles"] = {
                "seconds": round(time.perf_counter() - _dbg_t0, 4),
                "matches": len(matches),
                "document_chars": len(document),
                "data_not_found": expected_data,
                "tile": tile_name,
                "per_tile_regex_searches": _dbg_regex_searches + 1,
                "fast_lut": True,
                "lut_from_full_document": _lut_from_full_doc,
                "bucket_size": len(bucket),
                "bucket_sample": sample_bucket,
            }
            return False
        if expected_data:
            _dbg_regex_searches += 1

    #region debug-point (infobim-view-slow-crash): persist full success metric
    _DBG_METRICS["has_assembled_tiles"] = {
        "seconds": round(time.perf_counter() - _dbg_t0, 4),
        "matches": len(matches),
        "document_chars": len(document),
        "ok": True,
        "per_tile_regex_searches": _dbg_regex_searches,
        "fast_lut": True,
        "lut_from_full_document": _lut_from_full_doc,
    }
    #endregion
    return True


_SURFACE_OPEN_RE: Any = re.compile(
    rf"<{SURFACE_TAG}\b[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_SURFACE_CLOSE_RE: Any = re.compile(
    rf"</{SURFACE_TAG}\s*>",
    re.IGNORECASE,
)
_TILE_ATTRS_RE: Any = re.compile(
    r"<(?P<tag>[A-Za-z][A-Za-z0-9._:-]*)"
    r"(?P<attrs>\s[^<>]*?)>",
    re.DOTALL,
)
_ATTR_RE: Any = re.compile(
    r"""
    (?P<name>[a-z_:][\w:.-]*)\s*=\s*
    (?:
        "(?P<dq>[^"\\]*(?:\\.[^"\\]*)*)"
      | '(?P<sq>[^'\\]*(?:\\.[^'\\]*)*)'
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _extract_surface_inner_markup(document: str) -> Optional[str]:
    # Always take the LAST occurrence to avoid matching commented-out stubs
    # or stale pre-assembly tag copies that some HTML builders leave in the
    # head. Using max() on match.span() gives us the rightmost real tag.
    open_matches = list(_SURFACE_OPEN_RE.finditer(document))
    if not open_matches:
        return None
    open_match = open_matches[-1]
    close_matches = list(_SURFACE_CLOSE_RE.finditer(document, open_match.end()))
    if not close_matches:
        # Fallback: accept any close-match later in the doc (could be wrong,
        # but it's strictly better than returning None which triggers the
        # O(matches · document_chars) legacy scan that costs 5+ minutes).
        any_close = list(_SURFACE_CLOSE_RE.finditer(document))
        if not any_close or any_close[-1].start() <= open_match.end():
            return None
        close_match = any_close[-1]
    else:
        close_match = close_matches[0]
    return document[open_match.end():close_match.start()]


def _build_tile_lut(
    surface_inner: str,
) -> Optional[Dict[tuple[str, str], Set[str]]]:
    """Return a dict of (tag, region) → {resourceId1, resourceId2, ...} from
    the tile tags inside the surface element's light DOM.

    Multiple tiles with the same (tag, region) pair are perfectly valid — for
    example 1000+ <onto-image-file-tile surface-region=content> tiles all in
    the content region, each pointing to a different photo resource. The LUT
    therefore accumulates a set of all resource ids observed for each key
    instead of only the last one (the prior bug that caused 100% reproducible
    MISMATCH failures for any real project with multiple tiles of the same
    type in the same region).

    Single O(surface_inner_chars) pass replacing the previous O(matches ·
    document_chars) regex scan. For 2000 tiles in a 10 MB document this
    reduces ~40 GB of string scans to a single 50-200 KB scan.
    """
    lut: Dict[tuple[str, str], Set[str]] = {}
    for match in _TILE_ATTRS_RE.finditer(surface_inner):
        tag: str = match.group("tag").lower()
        attrs_str: str = match.group("attrs")
        region: Optional[str] = None
        resource: str = ""
        if tag == SURFACE_TAG.lower():
            continue
        for attr in _ATTR_RE.finditer(attrs_str):
            name: str = attr.group("name").lower()
            value: str = attr.group("dq") if attr.group("dq") is not None else attr.group("sq")
            if value is None:
                continue
            if name == "surface-region":
                region = value
            elif name == "data-ontobdc-resource":
                resource = value
        if region is None:
            continue
        key: tuple[str, str] = (tag, region.lower())
        bucket: Optional[Set[str]] = lut.get(key)
        if bucket is None:
            bucket = set()
            lut[key] = bucket
        bucket.add(resource)
    return lut


def has_packaged_runtime(document: str) -> bool:
    if contains_external_runtime_reference(document):
        return False
    return re.search(
        r"<script\b[^>]*\bdata-ontobdc-surface-component(?:=|\s|>)",
        document,
        re.IGNORECASE,
    ) is not None


def is_enriched_surface(document: str) -> bool:
    return has_initialized_surface(document) and has_jsonld(document)


def is_set_surface(document: str) -> bool:
    return is_enriched_surface(document) and has_surface_config(document)


def is_matched_surface(document: str) -> bool:
    return is_set_surface(document) and has_surface_matches(document)


def is_operational_matched_surface(document: str) -> bool:
    return is_matched_surface(document) and has_valid_default_layouts(document)


def is_assembled_surface(document: str) -> bool:
    return is_operational_matched_surface(document) and has_assembled_tiles(document)


def is_packaged_surface(document: str) -> bool:
    return is_assembled_surface(document) and has_packaged_runtime(document)


def is_valid_surface(document: str) -> bool:
    return is_packaged_surface(document)
