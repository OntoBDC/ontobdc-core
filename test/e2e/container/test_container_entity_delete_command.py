"""Installed CLI routing for `container --entity <id> --delete`; failure must precede ETL."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerEntityDeleteCommand:
    def test_container_help_lists_entity_delete_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--delete" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "abc"),
            ("--delete",),
            ("--entity", "--delete"),
            ("--entity", "abc", "--delete", "extra"),
            ("--entity", "abc", "--delete", "--unknown", "value"),
            ("--entity", "abc", "--entity", "def", "--delete"),
        ],
    )
    def test_invalid_entity_delete_route_does_not_remove_entities(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("container", *args)

        assert result.exit_code != 0, result.stdout
        assert "Entity Deleted" not in result.stdout
        assert workspace.snapshot() == before

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "abc", "--delete"),
            ("--entity", "abc", "--delete", "--container", "urn:uuid:00000000-0000-4000-8000-000000000000"),
            ("--container", "urn:uuid:00000000-0000-4000-8000-000000000000", "--entity", "abc", "--delete"),
        ],
    )
    def test_valid_entity_delete_route_fails_immediately_without_repository(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        args: Tuple[str, ...],
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run("container", *args)

        assert result.exit_code != 0
        assert "EntityRepositoryNotInjectedError" in result.stdout + result.stderr
        assert workspace.snapshot() == before
