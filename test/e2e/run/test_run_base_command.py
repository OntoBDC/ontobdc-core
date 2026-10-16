"""Installed CLI routing for the bare `run` component and its help flags."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcRunBaseCommand:
    def test_run_help_lists_run_commands(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--capability" in result.stdout
        assert "--fsm" in result.stdout
        assert "--tag" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("--help",),
            ("-h",),
        ],
    )
    def test_bare_run_returns_help_response(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run", *args)
        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Run Commands"
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--help", "--extra"),
            ("-h", "--unknown"),
        ],
    )
    def test_bare_run_rejects_extra_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run", *args)
        assert result.exit_code != 0, result.stdout
        assert "Run Commands" not in result.stdout
