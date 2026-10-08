import json
from pathlib import Path
from typing import Any, Dict

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContainerUpdateCommand:
    """
    E2E coverage for `ontobdc container --update <source> --json`.

    The source is accepted in three shapes: a .csv file, a .json file, or
    inline key=value assignments. A source that parses is written into the
    container the command resolves from the working directory, and the fields
    it may carry are the ones the container facade declares as editable.
    """

    def _container(self, cli_runner: OntobdcCliProcessRunner) -> None:
        """
        Register the isolated project root itself as a container.

        The command resolves its container from the working directory, and the
        runner scopes every invocation to the project root, so the root is
        where a container has to be for these tests to reach one.
        """
        assert cli_runner.run("init").exit_code == 0
        assert cli_runner.run("container", "--create", ".").exit_code == 0

    def _error_of(self, result: CliInvocationResult) -> str:
        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"

        return str(payload["content"]["error"])

    def test_an_update_without_a_container_to_write_to_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "title=Sem Container"
        )

        assert result.exit_code == 1
        assert "Missing required input: container_id" in self._error_of(result)

    # ------------------------------------------------------------------
    # Routing: the command is not reached at all
    # ------------------------------------------------------------------

    def test_update_without_a_source_flag_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", "--update")

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    def test_source_flag_without_a_value_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", "--update")

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    # ------------------------------------------------------------------
    # Sources that are not one of the three shapes
    # ------------------------------------------------------------------

    def test_a_bare_word_is_not_a_source(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "so-texto"
        )

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    def test_an_empty_source_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", ""
        )

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    # ------------------------------------------------------------------
    # Sources of an accepted shape whose content does not parse
    # ------------------------------------------------------------------

    def test_a_missing_json_file_is_reported_by_path(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "ausente.json"
        )

        assert result.exit_code == 1
        assert self._error_of(result) == (
            "Container update source file not found: ausente.json"
        )

    def test_a_missing_csv_file_is_reported_by_path(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "ausente.csv"
        )

        assert self._error_of(result) == (
            "Container update source file not found: ausente.csv"
        )

    def test_a_json_source_that_is_not_an_object_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "list.json"
        source.write_text(json.dumps(["title", "description"]), encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "list.json"
        )

        assert self._error_of(result) == (
            "Container update JSON source must contain an object."
        )

    def test_a_csv_source_with_more_than_one_row_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "rows.csv"
        source.write_text("title\nPrimeiro\nSegundo\n", encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "rows.csv"
        )

        assert self._error_of(result) == (
            "Container update CSV source must contain exactly one data row."
        )

    def test_a_csv_source_with_only_a_header_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        source: Path = tmp_path / "header.csv"
        source.write_text("title,description\n", encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "header.csv"
        )

        assert self._error_of(result) == (
            "Container update CSV source must contain exactly one data row."
        )

    def test_an_assignment_without_a_key_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "=semchave"
        )

        assert self._error_of(result) == (
            "Invalid container update assignment: =semchave"
        )

    def test_a_repeated_assignment_key_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "title=A,title=B"
        )

        assert self._error_of(result) == "Duplicate container update key: title"
