"""
Installed CLI routing for `context --suggestion [--container <id>]`.

The suggestion pipeline opens an interactive approval TUI when it runs
against a real container, which cannot be exercised headless. The tests
below therefore cover routing and the check stage: routes that name no
resolvable container must be rejected before the FSM starts.
"""

from typing import Tuple

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContextSuggestionCommand:
    def test_context_help_lists_suggestion_command(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context")
        assert result.exit_code == 0, result.stdout + result.stderr
        assert "Suggest" in result.stdout

    @pytest.mark.parametrize(
        "args",
        [
            ("--container", "urn:uuid:00000000-0000-4000-8000-000000000000"),
            ("--suggestion", "--extra", "x"),
            ("--suggestion", "--container"),
            ("--suggestion", "--container", ""),
            ("--unknown",),
        ],
    )
    def test_invalid_suggestion_route_fails(
        self,
        cli_runner: OntobdcCliProcessRunner,
        args: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", *args)
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    def test_suggestion_without_container_fails_at_check(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("context", "--suggestion")
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout

    def test_suggestion_with_unresolvable_container_fails_at_check(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "context",
            "--suggestion",
            "--container",
            "urn:uuid:00000000-0000-4000-8000-000000000000",
        )
        assert result.exit_code != 0, result.stdout
        assert "Invalid command arguments" in result.stdout
