from pathlib import Path
from typing import Any, Dict, List

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcInitCommand:
    """
    E2E coverage for `ontobdc init --json`.

    `init` writes `.__ontobdc__/{config.yaml,context.ttl,storage.ttl}` into
    the current directory, so every invocation here runs through
    `cli_runner`, which scopes the process's cwd to a fresh pytest
    `tmp_path` -- never the developer's real project directories.
    """

    def test_init_bootstraps_ontobdc_directory_in_isolated_root(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        result: CliInvocationResult = cli_runner.run("init")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Init"
        assert payload["severity"] is None

        content: Dict[str, Any] = payload["content"]
        assert Path(content["root_path"]).resolve() == tmp_path.resolve()
        assert Path(content["ontobdc_directory"]).resolve() == (tmp_path / ".__ontobdc__").resolve()

        visited_states: List[str] = content["visited_states"]
        assert "__brand_ready__" in visited_states
        assert content["current_state"] == "__brand_ready__"

    def test_init_writes_only_inside_the_isolated_root(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")

        ontobdc_directory: Path = tmp_path / ".__ontobdc__"
        assert (ontobdc_directory / "config.yaml").is_file()
        assert (ontobdc_directory / "context.ttl").is_file()
        assert (ontobdc_directory / "storage.ttl").is_file()

        created_entries: List[Path] = list(tmp_path.iterdir())
        assert created_entries == [ontobdc_directory]

    def test_init_is_idempotent_when_run_twice(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        first_result: CliInvocationResult = cli_runner.run("init")
        second_result: CliInvocationResult = cli_runner.run("init")

        assert first_result.exit_code == 0
        assert second_result.exit_code == 0
        assert second_result.json["content"]["current_state"] == "__brand_ready__"
