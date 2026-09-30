from typing import Any, Dict

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcHelpCommand:
    """
    E2E coverage for `ontobdc --help --json` / `ontobdc -h --json`.

    Help is its own command, not the bare `ontobdc` one: it answers with a
    one-line summary per top-level command instead of the full command
    tree the bare entrypoint prints.
    """

    @pytest.mark.parametrize("help_flag", ["--help", "-h"])
    def test_help_flag_returns_command_summaries(
        self,
        cli_runner: OntobdcCliProcessRunner,
        help_flag: str,
    ) -> None:
        result: CliInvocationResult = cli_runner.run(help_flag)

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "OntoBDC Help"
        assert payload["severity"] is None

        documented_commands: Dict[str, str] = payload["content"]["Commands"]
        assert isinstance(documented_commands, dict)
        for expected_command in ("container", "run"):
            assert expected_command in documented_commands
            assert documented_commands[expected_command].strip() != ""

    def test_help_flag_differs_from_bare_command(self, cli_runner: OntobdcCliProcessRunner) -> None:
        help_payload: Dict[str, Any] = cli_runner.run("--help").json
        bare_payload: Dict[str, Any] = cli_runner.run().json

        assert bare_payload["title"] == "OntoBDC Commands"
        assert help_payload["title"] != bare_payload["title"]
        assert help_payload["content"]["Commands"] != bare_payload["content"]["Commands"]

    def test_help_flag_with_extra_argument_fails_with_exit_code_one(
        self,
        cli_runner: OntobdcCliProcessRunner,
    ) -> None:
        result: CliInvocationResult = cli_runner.run("--help", "extra")

        assert result.exit_code == 1

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"
