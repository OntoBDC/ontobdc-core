"""Installed CLI routing for the bare `context` component and its help flags."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContextBaseCommand:
    def test_context_help_lists_context_commands(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--term" in result.stdout
        assert "--inspect" in result.stdout
        assert "--pdf-to-graph" in result.stdout
        assert "Suggest" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("--help",),
            ("-h",),
        ],
    )
    def test_bare_context_returns_help_response(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Context Commands"
        assert "Commands" in result.json["content"]

    @pytest.mark.parametrize(
        "args",
        [
            ("--unknown",),
            ("--help", "--extra"),
            ("-h", "--unknown"),
        ],
    )
    def test_bare_context_rejects_extra_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code != 0, result.stdout
        assert "Context Commands" not in result.stdout
