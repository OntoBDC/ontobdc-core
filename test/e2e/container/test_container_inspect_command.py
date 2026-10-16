"""Installed CLI routing for `container --inspect` (static container inspection)."""

from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerInspectCommand:
    def test_container_help_lists_inspect_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--inspect" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--inspect", "value"),
            ("--inspect", "--unknown"),
            ("--container",),
            ("--container", "id", "--inspect", "extra"),
            ("--inspect", "--container"),
        ],
    )
    def test_invalid_inspect_route_fails_without_inspecting(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Container Inspection" not in result.stdout

    @pytest.mark.parametrize("selector", ["cwd", "id"])
    def test_inspect_reports_a_registered_container_without_modifying_it(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        selector: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        if selector == "cwd":
            result: CliInvocationResult = workspace.runner().run(
                "container", "--inspect"
            )
        else:
            result = cli_runner.run(
                "container", "--container", workspace.identifier, "--inspect"
            )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Inspection"
        content: Dict[str, Any] = result.json["content"]
        assert "tree" in content
        assert content["tree"]["name"] == "container"
        assert workspace.snapshot() == before
