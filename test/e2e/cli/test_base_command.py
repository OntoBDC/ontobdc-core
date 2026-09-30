from typing import Any, Dict

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcBaseCommand:
    """
    E2E coverage for the bare `ontobdc` entrypoint: no subcommand and
    unknown-argument handling. Every invocation runs the real installed
    executable through a subprocess, always with `--json`. `--help`/`-h`
    and `--version`/`-v` are separate commands with their own dedicated
    coverage in `test_help_command.py` and `test_version_command.py`.
    """

    def test_no_arguments_lists_available_commands(self, cli_runner: OntobdcCliProcessRunner) -> None:
        result: CliInvocationResult = cli_runner.run()

        assert result.exit_code == 0
        assert result.stderr.strip() == "" or "Traceback" not in result.stderr

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "OntoBDC Commands"
        assert payload["severity"] is None

        commands_tree: str = payload["content"]["Commands"]
        for expected_command in ("container", "init", "run", "--version"):
            assert expected_command in commands_tree

    def test_unknown_command_fails_with_exit_code_one(self, cli_runner: OntobdcCliProcessRunner) -> None:
        result: CliInvocationResult = cli_runner.run("foobar")

        assert result.exit_code == 1

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"
        assert "foobar" in payload["content"]["error"]

    def test_unknown_flag_fails_with_exit_code_one(self, cli_runner: OntobdcCliProcessRunner) -> None:
        result: CliInvocationResult = cli_runner.run("--bogus-flag")

        assert result.exit_code == 1

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"
        assert "--bogus-flag" in payload["content"]["error"]
