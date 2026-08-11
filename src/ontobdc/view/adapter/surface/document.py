import html
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


STATE_META_NAME = "ontobdc:surface-state"
JSONLD_ID = "ontobdc-surface-jsonld"
CONFIG_ID = "ontobdc-surface-config"
MATCHES_ID = "ontobdc-surface-matches"
COMPONENT_SCRIPT_ATTR = "data-ontobdc-surface-component"
SURFACE_TAG = "onto-presentation-surface"
_CUSTOM_ELEMENT_RE = re.compile(r"^[a-z][a-z0-9._-]*-[a-z0-9._-]+$")


def resolve_surface_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
        raise ValueError("surface_path is required")
    return Path(raw_path).expanduser().resolve()


def read_surface(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_surface(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_initial_html(lang: str = "en") -> str:
    safe_lang = html.escape(lang or "en", quote=True)
    return f'''<!doctype html>
<html lang="{safe_lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="{STATE_META_NAME}" content="surface_initialized">
  <title>OntoBDC Presentation Surface</title>
</head>
<body>
  <{SURFACE_TAG}></{SURFACE_TAG}>
</body>
</html>
'''


def _insert_before_closing_tag(document: str, tag: str, insertion: str) -> str:
    closing = f"</{tag}>"
    if closing not in document:
        raise ValueError(
            f"Surface document is missing a closing <{tag}> tag; "
            "refusing to insert content into a malformed document."
        )
    return document.replace(closing, f"  {insertion}\n{closing}", 1)


def set_state_marker(document: str, state_name: str) -> str:
    marker = (
        f'<meta name="{STATE_META_NAME}" '
        f'content="{html.escape(state_name, quote=True)}">'
    )
    pattern = re.compile(
        rf"<meta\s+name=[\"']{re.escape(STATE_META_NAME)}[\"']"
        rf"\s+content=[\"'][^\"']*[\"']\s*/?>",
        re.IGNORECASE,
    )
    if pattern.search(document):
        return pattern.sub(marker, document, count=1)
    return _insert_before_closing_tag(document, "head", marker)


def get_state_marker(document: str) -> Optional[str]:
    pattern = re.compile(
        rf"<meta\s+name=[\"']{re.escape(STATE_META_NAME)}[\"']"
        rf"\s+content=[\"']([^\"']+)[\"']\s*/?>",
        re.IGNORECASE,
    )
    match = pattern.search(document)
    return match.group(1).strip() if match else None


def _json_script(
    script_id: str,
    payload: Any,
    script_type: str = "application/json",
) -> str:
    body = json.dumps(payload, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="{script_type}" id="{script_id}">\n{body}\n</script>'


def upsert_json_script(
    document: str,
    script_id: str,
    payload: Any,
    script_type: str = "application/json",
) -> str:
    replacement = _json_script(script_id, payload, script_type)
    pattern = re.compile(
        rf"<script\b[^>]*\bid=[\"']{re.escape(script_id)}[\"'][^>]*>"
        rf".*?</script>",
        re.IGNORECASE | re.DOTALL,
    )
    if pattern.search(document):
        return pattern.sub(replacement, document, count=1)
    return _insert_before_closing_tag(document, "head", replacement)


def extract_json_script(document: str, script_id: str) -> Any:
    pattern = re.compile(
        rf"<script\b[^>]*\bid=[\"']{re.escape(script_id)}[\"'][^>]*>"
        rf"(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(document)
    if not match:
        raise ValueError(f"Missing script: {script_id}")
    return json.loads(match.group(1).replace("<\\/", "</"))


def normalize_surface_config(raw: Any) -> Dict[str, Any]:
    source: Dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else {}
    content = (
        source.get("content")
        if isinstance(source.get("content"), Mapping)
        else {}
    )
    operation = (
        source.get("operation")
        if isinstance(source.get("operation"), Mapping)
        else {}
    )
    pinned = (
        source.get("pinned")
        if isinstance(source.get("pinned"), Mapping)
        else {}
    )

    mode = str(content.get("mode", "scroll")).strip().lower()
    if mode not in {"scroll", "fixed"}:
        raise ValueError("surface content mode must be 'scroll' or 'fixed'")

    return {
        "operation": {"enabled": bool(operation.get("enabled", True))},
        "content": {"mode": mode},
        "pinned": {"enabled": bool(pinned.get("enabled", True))},
        "slotTarget": _positive_number(source.get("slotTarget"), 72),
        "gap": _non_negative_number(source.get("gap"), 12),
        "padding": _non_negative_number(source.get("padding"), 16),
        "tileMargin": _non_negative_number(source.get("tileMargin"), 0),
    }


def normalize_matches(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("surface_matches must be a list")

    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"surface_matches[{index}] must be an object")

        tile = str(item.get("tile", "")).strip().lower()
        if not _CUSTOM_ELEMENT_RE.fullmatch(tile):
            raise ValueError(
                f"surface_matches[{index}].tile must be a valid custom-element tag"
            )

        region = str(item.get("region", "content")).strip().lower()
        if region not in {"operation", "content", "pinned"}:
            raise ValueError(f"surface_matches[{index}].region is invalid")

        data_id = str(item.get("data", item.get("data_id", ""))).strip()

        min_columns = _positive_int(item.get("minColumns"), 1)
        preferred_columns = _positive_int(
            item.get("preferredColumns"),
            min_columns,
        )
        max_columns = _positive_int(
            item.get("maxColumns"),
            preferred_columns,
        )
        min_rows = _positive_int(item.get("minRows"), 1)
        preferred_rows = _positive_int(item.get("preferredRows"), min_rows)
        max_rows = _positive_int(item.get("maxRows"), preferred_rows)

        if not (min_columns <= preferred_columns <= max_columns):
            raise ValueError(
                f"surface_matches[{index}] has invalid column envelope"
            )
        if not (min_rows <= preferred_rows <= max_rows):
            raise ValueError(
                f"surface_matches[{index}] has invalid row envelope"
            )
        if region in {"operation", "pinned"} and (
            min_rows != 1 or preferred_rows != 1 or max_rows != 1
        ):
            raise ValueError(
                f"surface_matches[{index}] fixed-region Tiles must be one row high"
            )

        normalized_item: Dict[str, Any] = {
            **dict(item),
            "tile": tile,
            "region": region,
            "minColumns": min_columns,
            "preferredColumns": preferred_columns,
            "maxColumns": max_columns,
            "minRows": min_rows,
            "preferredRows": preferred_rows,
            "maxRows": max_rows,
        }
        if data_id:
            normalized_item["data"] = data_id
        else:
            normalized_item.pop("data", None)
            normalized_item.pop("data_id", None)
        normalized.append(normalized_item)

    return normalized


def assemble_surface_markup(
    document: str,
    matches: Iterable[Mapping[str, Any]],
) -> str:
    surface_pattern = re.compile(
        rf"<{SURFACE_TAG}\b[^>]*>.*?</{SURFACE_TAG}>",
        re.IGNORECASE | re.DOTALL,
    )
    tiles: List[str] = []
    for match in matches:
        attrs: Dict[str, Any] = {
            "surface-region": match["region"],
            "min-columns": match["minColumns"],
            "columns": match["preferredColumns"],
            "max-columns": match["maxColumns"],
            "min-rows": match["minRows"],
            "rows": match["preferredRows"],
            "max-rows": match["maxRows"],
        }
        data_id = str(match.get("data", "")).strip()
        if data_id:
            attrs["data-ontobdc-resource"] = data_id
        if match.get("closed"):
            attrs["data-tile-closed"] = "true"

        attr_text = " ".join(
            f'{name}="{html.escape(str(value), quote=True)}"'
            for name, value in attrs.items()
        )
        tile_name = str(match["tile"])
        tiles.append(f"    <{tile_name} {attr_text}></{tile_name}>")

    surface = (
        f"<{SURFACE_TAG}>\n"
        + "\n".join(tiles)
        + f"\n  </{SURFACE_TAG}>"
    )
    if surface_pattern.search(document):
        return surface_pattern.sub(surface, document, count=1)
    return _insert_before_closing_tag(document, "body", surface)


def embed_component_scripts(
    document: str,
    scripts: Iterable[str],
) -> str:
    without_existing = re.sub(
        rf"\s*<script\b[^>]*\b{COMPONENT_SCRIPT_ATTR}"
        rf"(?:=[\"'][^\"']*[\"'])?[^>]*>.*?</script>\s*",
        "\n",
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    blocks: List[str] = []
    for index, script in enumerate(scripts):
        if not isinstance(script, str) or not script.strip():
            continue
        safe_script = script.replace("</script>", "<\\/script>")
        blocks.append(
            f'<script type="module" {COMPONENT_SCRIPT_ATTR}="{index}">\n'
            f"{safe_script}\n</script>"
        )
    insertion = "\n  ".join(blocks)
    if not insertion:
        return without_existing
    return _insert_before_closing_tag(without_existing, "body", insertion)


def contains_external_runtime_reference(document: str) -> bool:
    patterns = [
        r"<script\b[^>]*\bsrc=[\"']\s*https?://",
        r"<link\b[^>]*\bhref=[\"']\s*https?://",
        r"@import\s+(?:url\()?\s*[\"']?https?://",
    ]
    return any(re.search(pattern, document, re.IGNORECASE) for pattern in patterns)


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _positive_number(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _non_negative_number(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback
