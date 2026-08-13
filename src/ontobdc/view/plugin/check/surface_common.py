import json
import re
from pathlib import Path
from typing import Optional

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
    if re.search(
        rf"<{SURFACE_TAG}\b[^>]*\bdata-ontobdc-assembled=[\"']true[\"']",
        document,
        re.IGNORECASE,
    ) is None:
        return False

    try:
        matches = extract_json_script(document, MATCHES_ID)
    except (ValueError, json.JSONDecodeError):
        return False
    if not isinstance(matches, list):
        return False

    for item in matches:
        if not isinstance(item, dict):
            return False
        tile_name = str(item.get("tile", "")).strip()
        region = str(item.get("region", "")).strip()
        if not tile_name or not region:
            return False

        tile = re.escape(tile_name)
        region_value = re.escape(region)
        pattern = rf"<{tile}\b[^>]*\bsurface-region=[\"']{region_value}[\"']"
        match = re.search(pattern, document, re.IGNORECASE)
        if match is None:
            return False

        data_id = str(item.get("data", "")).strip()
        if data_id:
            data_pattern = (
                rf"<{tile}\b[^>]*\bdata-ontobdc-resource=[\"']"
                rf"{re.escape(data_id)}[\"']"
            )
            if re.search(data_pattern, document, re.IGNORECASE) is None:
                return False

    return True


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
