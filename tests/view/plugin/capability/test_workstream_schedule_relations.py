from pathlib import Path

from ontobdc.view.plugin.capability.workstream_schedule_relations import (
    are_workstream_schedule_relations_materialized,
    materialize_workstream_schedule_relations,
    workstream_schedule_relations,
)


WORKSTREAM_URI = (
    "urn:infobim:workstream/"
    "7c7e9d91-046d-5bcb-ad09-a04c5821c6de"
)
SCHEDULE_URI = (
    "urn:infobim:ifc-work-schedule/"
    "69240f56-8e7a-401a-93cc-c43e12d9c72e"
)


def _write_fixture(container_path: Path) -> None:
    linkset_path = (
        container_path
        / ".workstream"
        / ".__ontobdc__"
        / "linkset"
        / "WorkStreamSchedule.ttl"
    )
    linkset_path.parent.mkdir(parents=True)
    linkset_path.write_text(
        f'''@prefix ls: <https://standards.iso.org/iso/21597/-1/ed-1/en/Linkset#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<urn:test:link> a ls:DirectedBinaryLink ;
    ls:hasFromLinkElement <urn:test:from> ;
    ls:hasToLinkElement <urn:test:to> .

<urn:test:from> a ls:LinkElement ;
    ls:hasIdentifier <urn:test:from-id> .

<urn:test:from-id> a ls:URIBasedIdentifier ;
    ls:uri "{WORKSTREAM_URI}/dimension/when"^^xsd:anyURI .

<urn:test:to> a ls:LinkElement ;
    ls:hasIdentifier <urn:test:to-id> .

<urn:test:to-id> a ls:URIBasedIdentifier ;
    ls:uri "{SCHEDULE_URI}"^^xsd:anyURI .
''',
        encoding="utf-8",
    )
    asset_directory = (
        container_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
        / "js"
    )
    asset_directory.mkdir(parents=True)
    (asset_directory / "pyodide_bootstrap.js").write_text(
        'async function loadWorkstreamBoardModule() {\n'
        '    loadStyle("../css/workstream_board.css");\n'
        '    await loadScript("workstream_schedule_relations.js");\n'
        '    await loadScript("workstream_board.js");\n'
        '    await loadScript("workstream_schedule_board.js");\n'
        '}\n',
        encoding="utf-8",
    )
    (asset_directory / "workstream_board.js").write_text(
        "window.oldWorkstreamBoard = true;\n",
        encoding="utf-8",
    )
    (asset_directory / "workstream_schedule_board.js").write_text(
        "window.duplicateScheduleBoard = true;\n",
        encoding="utf-8",
    )


def test_reads_when_dimension_schedule_relation(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    assert workstream_schedule_relations(tmp_path) == {
        WORKSTREAM_URI: [SCHEDULE_URI],
    }


def test_materializes_single_compact_board_runtime(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = materialize_workstream_schedule_relations(tmp_path)

    assert result["workstream_schedule_relation_count"] == 1
    assert are_workstream_schedule_relations_materialized(tmp_path)
    asset_root = (
        tmp_path
        / ".__ontobdc__"
        / "asset"
        / "infobim-view"
    )
    js_directory = asset_root / "js"
    css_directory = asset_root / "css"
    bootstrap = (js_directory / "pyodide_bootstrap.js").read_text(
        encoding="utf-8"
    )
    board = (js_directory / "workstream_board.js").read_text(
        encoding="utf-8"
    )
    summary_css = (
        css_directory / "workstream_schedule_summary.css"
    ).read_text(encoding="utf-8")
    assert 'loadScript("workstream_schedule_relations.js")' in bootstrap
    assert 'loadScript("workstream_schedule_board.js")' not in bootstrap
    assert 'loadStyle("../css/workstream_schedule_summary.css")' in bootstrap
    assert not (js_directory / "workstream_schedule_board.js").exists()
    assert "linkedScheduleUris" in board
    assert "const calendarDayCount = 11;" in board
    assert "const previousCalendarDays = 5;" in board
    assert "const nextCalendarDays = 5;" in board
    assert "BusinessDay" not in board
    assert "const generalSchedules = scheduleUris(records);" in board
    assert ".filter((scheduleUri) => !linked.has(scheduleUri))" not in board
    assert '"2 / -1"' in board
    assert "grid-template-rows: 26px" in summary_css
    assert ".general-schedule-task-bar:first-child" in summary_css
