"""Installed CLI routing for `annotation --update`; failure must precede ETL."""

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def test_annotation_help_lists_update_command(tmp_path):
    result = OntobdcCliProcessRunner(tmp_path).run("annotate")
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Change the data of an annotation" in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--guid", "abc"),
        ("--title", "New"),
        ("--guid",),
        ("--guid", "abc", "--title",),
        ("--guid", "abc", "--unknown", "value"),
        ("--guid", "abc", "--guid", "def", "--title", "New"),
        ("--guid", "abc", "--container", "urn:uuid:00000000-0000-0000-0000-000000000000"),
        ("--guid", "--title", "New"),
    ],
)
def test_incomplete_or_invalid_update_route_does_not_create_artifacts(tmp_path, args):
    runner = OntobdcCliProcessRunner(tmp_path)
    result = runner.run("annotate", *args)
    assert "Annotation Updated" not in result.stdout
    assert not list(tmp_path.rglob("__annotations_created__.json"))
    assert not list(tmp_path.rglob("*.csv"))
    if args:
        assert result.exit_code != 0, result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("--guid", "abc", "--title", "New"),
        ("--title", "New", "--guid", "abc"),
        ("--guid", "abc", "--text", "Details"),
        ("--guid", "abc", "--author", "Elias"),
        ("--guid", "abc", "--type", "note"),
        ("--guid", "abc", "--title", "New", "--container", "urn:uuid:00000000-0000-0000-0000-000000000000"),
    ],
)
def test_valid_update_route_fails_immediately_without_repository(tmp_path, args):
    disk = ContainerE2eWorkspace.create(tmp_path)
    before = disk.snapshot()
    result = disk.runner().run("annotate", *args)
    assert result.exit_code != 0
    assert "EntityRepositoryNotInjectedError" in result.stdout + result.stderr
    assert disk.snapshot() == before
    assert not list(tmp_path.rglob("__annotations_created__.json"))
    assert not (disk.container / "annotation").exists()
