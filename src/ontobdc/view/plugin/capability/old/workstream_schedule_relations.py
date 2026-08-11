from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

METADATA_DIRECTORY = ".__ontobdc__"
RELATIONS_JSON_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "view"
    / "workstream_schedule_relations.json"
)
RELATIONS_JS_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "asset"
    / "infobim-view"
    / "js"
    / "workstream_schedule_relations.js"
)
BOARD_JS_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "asset"
    / "infobim-view"
    / "js"
    / "workstream_board.js"
)
SUMMARY_CSS_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "asset"
    / "infobim-view"
    / "css"
    / "workstream_schedule_summary.css"
)
STALE_BOARD_EXTENSION_JS_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "asset"
    / "infobim-view"
    / "js"
    / "workstream_schedule_board.js"
)
BOOTSTRAP_JS_RELATIVE_PATH = (
    Path(METADATA_DIRECTORY)
    / "asset"
    / "infobim-view"
    / "js"
    / "pyodide_bootstrap.js"
)
BOARD_SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "asset"
    / "js"
    / "workstream_board.js"
)
SUMMARY_CSS_SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "asset"
    / "css"
    / "workstream_schedule_summary.css"
)

LS = Namespace(
    "https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#"
)
WORKSTREAM_DIMENSION_SUFFIX = "/dimension/when"
IFC_WORK_SCHEDULE_PREFIX = "urn:infobim:ifc-work-schedule/"
_BOOTSTRAP_ORIGINAL = '    await loadScript("workstream_board.js");'
_BOOTSTRAP_REPLACEMENT = "\n".join(
    (
        '    await loadScript("workstream_schedule_relations.js");',
        '    await loadScript("workstream_board.js");',
    )
)
_BOOTSTRAP_LEGACY_REPLACEMENT = "\n".join(
    (
        '    await loadScript("workstream_schedule_relations.js");',
        '    await loadScript("workstream_board.js");',
        '    await loadScript("workstream_schedule_board.js");',
    )
)
_BOARD_STYLE_ORIGINAL = '    loadStyle("../css/workstream_board.css");'
_BOARD_STYLE_REPLACEMENT = "\n".join(
    (
        _BOARD_STYLE_ORIGINAL,
        '    loadStyle("../css/workstream_schedule_summary.css");',
    )
)


def _link_element_uri(graph: Graph, element: Any) -> str:
    if element is None:
        return ""
    identifier = graph.value(element, LS.hasIdentifier)
    if identifier is None:
        return ""
    value = graph.value(identifier, LS.uri)
    return str(value or "").strip()


def workstream_schedule_relations(
    container_path: Path,
) -> dict[str, list[str]]:
    """Read WorkStream When-dimension to IfcWorkSchedule links."""
    relations: dict[str, set[str]] = {}
    pattern = f"*/{METADATA_DIRECTORY}/linkset/*.ttl"
    for linkset_path in sorted(container_path.glob(pattern)):
        graph = Graph()
        try:
            graph.parse(linkset_path, format="turtle")
        except Exception as exc:
            raise ValueError(f"Invalid linkset: {linkset_path}") from exc
        for link in graph.subjects(RDF.type, LS.DirectedBinaryLink):
            source = _link_element_uri(
                graph,
                graph.value(link, LS.hasFromLinkElement),
            )
            target = _link_element_uri(
                graph,
                graph.value(link, LS.hasToLinkElement),
            )
            if not source.endswith(WORKSTREAM_DIMENSION_SUFFIX):
                continue
            if not target.startswith(IFC_WORK_SCHEDULE_PREFIX):
                continue
            workstream_uri = source[: -len(WORKSTREAM_DIMENSION_SUFFIX)]
            relations.setdefault(workstream_uri, set()).add(target)
    return {
        workstream_uri: sorted(schedule_uris)
        for workstream_uri, schedule_uris in sorted(relations.items())
    }


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _relations_json(relations: dict[str, list[str]]) -> str:
    return (
        json.dumps(
            relations,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _relations_js(relations: dict[str, list[str]]) -> str:
    return (
        "window.infoBimWorkStreamScheduleRelations = "
        + _relations_json(relations).strip()
        + ";\n"
    )


def _patched_bootstrap(content: str) -> str:
    patched = content
    if _BOOTSTRAP_LEGACY_REPLACEMENT in patched:
        patched = patched.replace(
            _BOOTSTRAP_LEGACY_REPLACEMENT,
            _BOOTSTRAP_REPLACEMENT,
            1,
        )
    elif _BOOTSTRAP_REPLACEMENT not in patched:
        if _BOOTSTRAP_ORIGINAL not in patched:
            raise ValueError(
                "The WorkStream board loader was not found in "
                "pyodide_bootstrap.js."
            )
        patched = patched.replace(
            _BOOTSTRAP_ORIGINAL,
            _BOOTSTRAP_REPLACEMENT,
            1,
        )

    if _BOARD_STYLE_REPLACEMENT not in patched:
        if _BOARD_STYLE_ORIGINAL not in patched:
            raise ValueError(
                "The WorkStream board stylesheet loader was not found in "
                "pyodide_bootstrap.js."
            )
        patched = patched.replace(
            _BOARD_STYLE_ORIGINAL,
            _BOARD_STYLE_REPLACEMENT,
            1,
        )
    return patched


def materialize_workstream_schedule_relations(
    container_path: Path,
) -> dict[str, Any]:
    """Publish relation data and one compact board runtime for the view."""
    relations = workstream_schedule_relations(container_path)
    json_path = container_path / RELATIONS_JSON_RELATIVE_PATH
    relation_js_path = container_path / RELATIONS_JS_RELATIVE_PATH
    board_js_path = container_path / BOARD_JS_RELATIVE_PATH
    summary_css_path = container_path / SUMMARY_CSS_RELATIVE_PATH
    stale_board_extension_path = (
        container_path / STALE_BOARD_EXTENSION_JS_RELATIVE_PATH
    )
    bootstrap_path = container_path / BOOTSTRAP_JS_RELATIVE_PATH
    if not bootstrap_path.is_file():
        raise ValueError(f"Dashboard bootstrap not found: {bootstrap_path}")
    if not BOARD_SOURCE_PATH.is_file():
        raise ValueError(
            "Integrated WorkStream board asset not found: "
            f"{BOARD_SOURCE_PATH}"
        )
    if not SUMMARY_CSS_SOURCE_PATH.is_file():
        raise ValueError(
            "WorkStream schedule summary stylesheet not found: "
            f"{SUMMARY_CSS_SOURCE_PATH}"
        )

    _atomic_write_text(json_path, _relations_json(relations))
    _atomic_write_text(relation_js_path, _relations_js(relations))
    _atomic_write_text(
        board_js_path,
        BOARD_SOURCE_PATH.read_text(encoding="utf-8"),
    )
    _atomic_write_text(
        summary_css_path,
        SUMMARY_CSS_SOURCE_PATH.read_text(encoding="utf-8"),
    )
    _atomic_write_text(
        bootstrap_path,
        _patched_bootstrap(
            bootstrap_path.read_text(encoding="utf-8")
        ),
    )
    stale_board_extension_path.unlink(missing_ok=True)
    return {
        "workstream_schedule_relation_count": sum(
            map(len, relations.values())
        ),
        "workstream_schedule_relations": relations,
        "workstream_schedule_relations_path": str(json_path),
    }


def are_workstream_schedule_relations_materialized(
    container_path: Path,
) -> bool:
    try:
        relations = workstream_schedule_relations(container_path)
        expected_json = _relations_json(relations)
        expected_js = _relations_js(relations)
        json_path = container_path / RELATIONS_JSON_RELATIVE_PATH
        relation_js_path = container_path / RELATIONS_JS_RELATIVE_PATH
        board_js_path = container_path / BOARD_JS_RELATIVE_PATH
        summary_css_path = container_path / SUMMARY_CSS_RELATIVE_PATH
        stale_board_extension_path = (
            container_path / STALE_BOARD_EXTENSION_JS_RELATIVE_PATH
        )
        bootstrap_path = container_path / BOOTSTRAP_JS_RELATIVE_PATH
        bootstrap = bootstrap_path.read_text(encoding="utf-8")
        return (
            json_path.read_text(encoding="utf-8") == expected_json
            and relation_js_path.read_text(encoding="utf-8")
            == expected_js
            and board_js_path.read_text(encoding="utf-8")
            == BOARD_SOURCE_PATH.read_text(encoding="utf-8")
            and summary_css_path.read_text(encoding="utf-8")
            == SUMMARY_CSS_SOURCE_PATH.read_text(encoding="utf-8")
            and _BOOTSTRAP_REPLACEMENT in bootstrap
            and _BOARD_STYLE_REPLACEMENT in bootstrap
            and _BOOTSTRAP_LEGACY_REPLACEMENT not in bootstrap
            and not stale_board_extension_path.exists()
        )
    except (OSError, UnicodeError, ValueError):
        return False
