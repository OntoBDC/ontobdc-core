"""Installed CLI routing for `container --entity <id> --update <source>`; failure must precede ETL."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerEntityUpdateCommand:
    def test_container_help_lists_entity_update_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--update" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "abc"),
            ("--update", "title=New"),
            ("--entity", "--update"),
            ("--entity", "abc", "--update"),
            ("--update", "title=New", "--entity"),
            ("--entity", "abc", "--update", "title=New", "extra"),
            ("--entity", "abc", "--update", "title=New", "--unknown", "value"),
            ("--entity", "abc", "--entity", "def", "--update", "title=New"),
        ],
    )
    def test_invalid_entity_update_route_does_not_modify_entities(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("container", *args)

        assert result.exit_code != 0, result.stdout
        assert "Entity Updated" not in result.stdout
        assert workspace.snapshot() == before
