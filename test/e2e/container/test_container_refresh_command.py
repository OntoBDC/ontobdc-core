import json
from typing import Any, Dict, List, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerRefreshCommand:
    @pytest.mark.parametrize("selector", ["cwd", "id", "path"])
    def test_refresh_synchronizes_added_files_and_preserves_user_content(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        selector: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        measurements: Path = workspace.container / "measurements.csv"
        measurements.write_text("value\n42\n", encoding="utf-8")
        assert "measurements.csv" not in workspace.manifest_files()
        result: CliInvocationResult
        if selector == "cwd":
            result = workspace.runner().run("container", "--refresh")
        else:
            result = cli_runner.run(
                "container", "--container", workspace.selector(selector), "--refresh"
            )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Storage Container Updated"
        content: Dict[str, Any] = result.json["content"]
        assert content["current_state"] == "__container_ro_crate_updated__"
        assert content["current_state"] in content["visited_states"]
        assert content["container_id"] == workspace.identifier
        assert "measurements.csv" in workspace.manifest_files()
        descriptor: Dict[str, Any] = json.loads(
            (workspace.container / ".__ontobdc__" / "datapackage.json").read_text(
                encoding="utf-8"
            )
        )
        resources: List[Dict[str, Any]] = descriptor["resources"]
        assert any(resource["path"] == "../measurements.csv" for resource in resources)
        assert measurements.read_bytes() == b"value\n42\n"

    def test_refresh_removes_stale_manifest_entries_after_a_file_is_deleted(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        removed: Path = workspace.container / "removed.csv"
        removed.write_text("value\n42\n", encoding="utf-8")
        synchronized: CliInvocationResult = workspace.runner().run(
            "container", "--refresh"
        )
        assert synchronized.exit_code == 0, synchronized.stdout
        assert "removed.csv" in workspace.manifest_files()
        removed.unlink()

        result: CliInvocationResult = workspace.runner().run("container", "--refresh")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert (
            result.json["content"]["current_state"] == "__container_ro_crate_updated__"
        )
        assert "removed.csv" not in workspace.manifest_files()
        assert not removed.exists()

    def test_refresh_cleans_stray_files_without_removing_user_files(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        stray: Path = workspace.container / ".DS_Store"
        stray.write_bytes(b"temporary desktop metadata")
        user_file: Path = workspace.container / "keep.txt"
        user_file.write_text("User content", encoding="utf-8")

        result: CliInvocationResult = workspace.runner().run("container", "--refresh")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert (
            result.json["content"]["current_state"] == "__container_ro_crate_updated__"
        )
        assert not stray.exists()
        assert user_file.read_text(encoding="utf-8") == "User content"

    def test_refresh_is_repeatable_without_duplicate_storage_entries(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        first: CliInvocationResult = workspace.runner().run("container", "--refresh")
        second: CliInvocationResult = workspace.runner().run("container", "--refresh")

        assert first.exit_code == 0, first.stdout
        assert second.exit_code == 0, second.stdout
        assert (
            first.json["content"]["container_id"]
            == second.json["content"]["container_id"]
            == workspace.identifier
        )
        assert (
            second.json["content"]["current_state"] == "__container_ro_crate_updated__"
        )
        listing: CliInvocationResult = OntobdcCliProcessRunner(workspace.root).run(
            "container"
        )
        assert listing.exit_code == 0, listing.stdout
        assert [entry["id"] for entry in listing.json["content"]["containers"]] == [
            workspace.identifier
        ]

    def test_refresh_requires_a_container(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("container", "--refresh")

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "arguments", [("--container", "--refresh"), ("--refresh", "extra")]
    )
    def test_refresh_rejects_invalid_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
