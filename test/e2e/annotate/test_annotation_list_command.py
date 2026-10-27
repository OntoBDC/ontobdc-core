"""Installed CLI routing for `annotation --list`; failure must precede ETL."""

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def test_annotation_help_lists_list_command(tmp_path):
    result = OntobdcCliProcessRunner(tmp_path).run("annotate")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "--list" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("--container",),
        ("--list", "--list"),
        ("--list", "--unknown"),
        ("--list", "--container"),
        ("--container", "urn:uuid:abc", "--list", "--extra", "value"),
    ],
)
def test_incomplete_or_invalid_list_route_does_not_create_artifacts(tmp_path, args):
    runner = OntobdcCliProcessRunner(tmp_path)
    result = runner.run("annotate", *args)
    assert "Annotations" not in result.stdout
    assert not list(tmp_path.rglob("*.csv"))
    assert result.exit_code != 0, result.stdout
