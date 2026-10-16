"""Installed CLI routing for `context --term <value> --inspect` (dictionary FSM)."""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContextDictionaryCommand:
    def test_context_help_lists_dictionary_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "--term" in result.stdout
        assert "--inspect" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--term", "house"),
            ("--inspect",),
            ("--term",),
            ("--term", "", "--inspect"),
            ("--term", "house", "--inspect", "--extra", "x"),
            ("--term", "house", "--inspect", "--unknown", "y"),
        ],
    )
    def test_invalid_dictionary_route_fails(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--term", "house", "--inspect"),
            ("--inspect", "--term", "house"),
        ],
    )
    def test_valid_dictionary_route_reaches_the_fsm(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        """
        The dictionary inspection FSM needs external model files. Without
        them the run stage fails, but routing and check must succeed: the
        response is a run-stage error, not an argument-routing error.
        """
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" not in result.stdout
        assert "CodeEvaluationError" in result.stdout
