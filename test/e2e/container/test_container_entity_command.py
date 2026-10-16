"""Installed CLI routing for `container --entity` (entity listing)."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerEntityCommand:
    def test_container_help_lists_entity_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--entity" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--entity", "value"),
            ("--entity", "--unknown"),
            ("--container",),
            ("--container", "id", "--entity", "extra"),
            ("--entity", "--container"),
        ],
    )
    def test_invalid_entity_route_fails_without_listing_entities(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Container Entities" not in result.stdout

    def test_entity_lists_datasets_of_a_registered_container(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = cli_runner.run(
            "container", "--container", workspace.identifier, "--entity"
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Entities"
        datasets: List[Dict[str, Any]] = result.json["content"]["datasets"]
        assert isinstance(datasets, list)
        assert workspace.snapshot() == before

    def test_entity_resolves_container_from_current_directory(
        self,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = workspace.runner().run("container", "--entity")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Entities"
        assert workspace.snapshot() == before
