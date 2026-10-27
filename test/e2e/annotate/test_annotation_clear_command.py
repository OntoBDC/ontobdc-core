"""Installed CLI routing for `annotation --clear`; failure must precede ETL."""

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def test_annotation_help_lists_clear_command(tmp_path):
    result = OntobdcCliProcessRunner(tmp_path).run("annotate")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "--clear" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--guid", "abc"),
        ("--clear", "text"),
        ("--guid",),
        ("--clear",),
        ("--guid", "abc", "--clear",),
        ("--guid", "abc", "--clear", "unknown"),
        ("--guid", "abc", "--clear", "text", "--unknown", "value"),
        ("--guid", "abc", "--guid", "def", "--clear", "text"),
        ("--clear", "--guid", "abc"),
    ],
)
def test_incomplete_or_invalid_clear_route_does_not_create_artifacts(tmp_path, args):
    runner = OntobdcCliProcessRunner(tmp_path)
    result = runner.run("annotate", *args)
    assert "Annotation Cleared" not in result.stdout
    assert not list(tmp_path.rglob("__annotations_created__.json"))
    assert not list(tmp_path.rglob("*.csv"))
    if args:
        assert result.exit_code != 0, result.stdout
