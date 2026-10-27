"""Installed CLI routing; failure must precede ETL and dataset creation."""

import pytest
from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def test_annotation_help_lists_point_command(tmp_path):
    result = OntobdcCliProcessRunner(tmp_path).run("annotate")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "--type" in result.stdout and "--point" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--type", "note"),
        ("--point", "drawing.dxf"),
        ("--type", "note", "--type", "note"),
        ("--type", "--point", "drawing.dxf"),
        ("--type", "note", "--point"),
        ("--type", "note", "--unknown", "drawing.dxf"),
    ],
)
def test_incomplete_or_invalid_route_does_not_create_artifacts(tmp_path, args):
    runner = OntobdcCliProcessRunner(tmp_path)
    result = runner.run("annotate", *args)
    assert "Annotation Created" not in result.stdout
    assert not list(tmp_path.rglob("__annotations_created__.json"))
    assert not list(tmp_path.rglob("*.csv"))
    if args:
        assert result.exit_code != 0, result.stdout
