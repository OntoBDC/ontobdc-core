"""Installed CLI routing for `container --list` (container listing)."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerListCommand:
    def test_container_help_lists_list_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--list" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--list", "value"),
            ("--list", "--unknown"),
            ("--unknown",),
        ],
    )
    def test_invalid_list_route_fails(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Containers" not in result.stdout

    def test_list_returns_zero_containers_for_a_fresh_storage(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("container", "--list")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Containers"
        containers: List[Dict[str, Any]] = result.json["content"]["containers"]
        assert containers == []

    def test_list_includes_a_registered_container(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run("container", "--list")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Containers"
        containers: List[Dict[str, Any]] = result.json["content"]["containers"]
        assert any(entry["id"] == workspace.identifier for entry in containers)

    def test_list_accepts_short_alias(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        ContainerE2eWorkspace.create(tmp_path)

        result: CliInvocationResult = cli_runner.run("container", "-l")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Containers"
