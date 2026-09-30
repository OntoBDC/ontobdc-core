from pathlib import Path
from typing import Any, Dict, List

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner


class TestOntobdcContainerCreateCommand:
    """
    E2E coverage for `ontobdc container --create <path> --json`.
    """

    def test_create_builds_a_new_container(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("container", "--create", "my-container")

        assert result.exit_code == 0

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Storage Container Created"
        assert payload["severity"] is None

        content: Dict[str, Any] = payload["content"]
        assert Path(content["path"]).resolve() == (tmp_path / "my-container").resolve()
        assert content["exists"] is True
        assert content["current_state"] == "__container_manifest_synced__"

        container_directory: Path = tmp_path / "my-container" / ".__ontobdc__"
        assert (container_directory / "container.ttl").is_file()

    def test_create_registers_the_container_in_the_storage_index(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        cli_runner.run("init")
        cli_runner.run("container", "--create", "my-container")

        list_result: CliInvocationResult = cli_runner.run("container")

        assert list_result.exit_code == 0
        containers: List[Dict[str, Any]] = list_result.json["content"]["containers"]
        assert len(containers) == 1
        assert containers[0]["location"] == str((tmp_path / "my-container").resolve())

    def test_create_without_a_path_is_rejected(self, cli_runner: OntobdcCliProcessRunner) -> None:
        cli_runner.run("init")
        result: CliInvocationResult = cli_runner.run("container", "--create")

        assert result.exit_code == 1

        payload: Dict[str, Any] = result.json
        assert payload["title"] == "Run Exception"
        assert "Invalid command arguments" in payload["content"]["error"]
