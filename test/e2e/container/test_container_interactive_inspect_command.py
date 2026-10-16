"""Installed CLI routing for `container --inspect --interactive` (TUI inspection).

The interactive surface opens a Textual TUI that cannot render in a headless
subprocess, so only the routing stage is exercised here: argument shapes that
the command accepts vs. those it rejects, plus the check-stage rejection when
no container can be resolved.
"""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContainerInteractiveInspectCommand:
    def test_container_help_lists_interactive_inspect_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--interactive" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--inspect",),
            ("--interactive",),
            ("-i",),
            ("--inspect", "--interactive", "value"),
            ("--inspect", "--interactive", "--unknown"),
            ("--container", "id", "--interactive"),
            ("--inspect", "-i", "--container"),
        ],
    )
    def test_invalid_interactive_inspect_route_is_rejected_at_routing(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--inspect", "--interactive"),
            ("--inspect", "-i"),
            ("-i", "--inspect"),
        ],
    )
    def test_interactive_inspect_requires_a_resolvable_container(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout
