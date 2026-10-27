"""Installed CLI routing for `annotation --export`; failure must precede ETL."""

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def test_annotation_help_lists_export_command(tmp_path):
    result = OntobdcCliProcessRunner(tmp_path).run("annotate")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "--export" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--export", "excel"),
        ("--type", "note"),
        ("--export",),
        ("--type",),
        ("--export", "excel", "--type",),
        ("--export", "--type", "note"),
        ("--export", "excel", "--export", "excel", "--type", "note"),
        ("--export", "excel", "--type", "note", "--unknown", "value"),
        ("--type", "note", "--type", "note", "--export", "excel"),
    ],
)
def test_incomplete_or_invalid_export_route_does_not_create_artifacts(tmp_path, args):
    runner = OntobdcCliProcessRunner(tmp_path)
    result = runner.run("annotate", *args)
    assert "Annotations Exported" not in result.stdout
    assert not list(tmp_path.rglob("__workbook_saved__.json"))
    assert not list(tmp_path.rglob("*.xlsx"))
    if args:
        assert result.exit_code != 0, result.stdout
