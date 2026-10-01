import json
from pathlib import Path
from typing import Any, Dict, List

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner

_UPDATED_TITLE: str = "Container Updated"


class TestOntobdcContainerUpdateCommand:
    """
    E2E coverage for `ontobdc container --update --from <source> --json`.

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

    def _title_in_listing(self, cli_runner: OntobdcCliProcessRunner) -> str:
        listing: CliInvocationResult = cli_runner.run("container")
        containers: List[Dict[str, Any]] = listing.json["content"]["containers"]
        assert len(containers) == 1

        return str(containers[0]["title"])

    def _error_of(self, result: CliInvocationResult) -> str:
        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"

        return str(payload["content"]["error"])

    def _persisted_of(self, result: CliInvocationResult) -> Dict[str, Any]:
        payload: Dict[str, Any] = result.json
        assert payload["title"] == _UPDATED_TITLE

        return dict(payload["content"]["result"])

    # ------------------------------------------------------------------
    # Sources that parse: the container is written and the listing follows
    # ------------------------------------------------------------------

    def test_inline_assignments_update_the_container(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        self._container(cli_runner)

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "title=Obra Central"
        )

        assert result.exit_code == 0
        assert self._persisted_of(result)["persisted"] is True
        assert self._title_in_listing(cli_runner) == "Obra Central"

    def test_an_update_writes_every_editable_field_it_carries(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        self._container(cli_runner)

        result: CliInvocationResult = cli_runner.run(
            "container",
            "--update",
            "--from",
            "title=Obra Central,description=Container da obra",
        )

        assert result.exit_code == 0
        listing: CliInvocationResult = cli_runner.run("container")
        container: Dict[str, Any] = listing.json["content"]["containers"][0]
        assert container["title"] == "Obra Central"
        assert container["description"] == "Container da obra"

    def test_json_file_updates_the_container(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        self._container(cli_runner)
        source: Path = tmp_path / "metadata.json"
        source.write_text(
            json.dumps({"title": "Vindo do JSON"}),
            encoding="utf-8",
        )

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "metadata.json"
        )

        assert result.exit_code == 0
        assert self._title_in_listing(cli_runner) == "Vindo do JSON"

    def test_csv_file_updates_the_container(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        self._container(cli_runner)
        source: Path = tmp_path / "metadata.csv"
        source.write_text(
            "title,description\nVindo do CSV,Descrição do CSV\n",
            encoding="utf-8",
        )

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "metadata.csv"
        )

        assert result.exit_code == 0
        assert self._title_in_listing(cli_runner) == "Vindo do CSV"

    def test_file_extension_is_matched_regardless_of_case(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        self._container(cli_runner)
        source: Path = tmp_path / "METADATA.JSON"
        source.write_text(json.dumps({"title": "Caixa Alta"}), encoding="utf-8")

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "METADATA.JSON"
        )

        assert result.exit_code == 0
        assert self._title_in_listing(cli_runner) == "Caixa Alta"

    # ------------------------------------------------------------------
    # Fields the facade does not let a user write
    # ------------------------------------------------------------------

    def test_a_field_the_facade_declares_as_not_editable_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        self._container(cli_runner)

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "created_at=2020-01-01T00:00:00"
        )

        assert result.exit_code == 1
        assert self._error_of(result) == (
            "The container facade declares 'created_at' as not editable."
        )

    def test_a_field_the_facade_does_not_declare_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        self._container(cli_runner)

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "cor=azul"
        )

        assert result.exit_code == 1
        assert self._error_of(result) == (
            "The container facade declares no field named 'cor'."
        )

    def test_an_update_without_a_container_to_write_to_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "title=Sem Container"
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
        result: CliInvocationResult = cli_runner.run("container", "--update", "--from")

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    # ------------------------------------------------------------------
    # Sources that are not one of the three shapes
    # ------------------------------------------------------------------

    def test_a_bare_word_is_not_a_source(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "so-texto"
        )

        assert result.exit_code == 1
        assert "Invalid command arguments" in self._error_of(result)

    def test_an_empty_source_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", ""
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
            "container", "--update", "--from", "ausente.json"
        )

        assert result.exit_code == 1
        assert self._error_of(result) == (
            "Container update source file not found: ausente.json"
        )

    def test_a_missing_csv_file_is_reported_by_path(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "ausente.csv"
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
            "container", "--update", "--from", "list.json"
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
            "container", "--update", "--from", "rows.csv"
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
            "container", "--update", "--from", "header.csv"
        )

        assert self._error_of(result) == (
            "Container update CSV source must contain exactly one data row."
        )

    def test_an_assignment_without_a_key_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "=semchave"
        )

        assert self._error_of(result) == (
            "Invalid container update assignment: =semchave"
        )

    def test_a_repeated_assignment_key_is_rejected(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--update", "--from", "title=A,title=B"
        )

        assert self._error_of(result) == "Duplicate container update key: title"
