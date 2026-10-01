from typing import Any, Dict, List
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerHealthCommand:
    @pytest.mark.parametrize("selector", ["cwd", "id", "path"])
    def test_health_reports_a_healthy_container_without_modifying_it(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        selector: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        storage_before: bytes = storage.read_bytes()
        result: CliInvocationResult
        if selector == "cwd":
            result = workspace.runner().run("container", "--health")
        else:
            result = cli_runner.run(
                "container", "--container", workspace.selector(selector), "--health"
            )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Health"
        assert result.json["severity"] == "SUCCESS"
        assert result.json["content"]["healthy"] is True
        checks: List[Dict[str, Any]] = result.json["content"]["checks"]
        assert {check["identifier"] for check in checks} >= {
            "container_metadata_ready",
            "container_storage_index_ready",
            "container_manifest_synced",
        }
        assert all(check["passed"] is True for check in checks)
        assert workspace.snapshot() == before
        assert storage.read_bytes() == storage_before

    def test_health_reports_manifest_drift_without_repairing_it(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "new.csv").write_text("value\n42\n", encoding="utf-8")
        before: Dict[str, bytes] = workspace.snapshot()

        result: CliInvocationResult = workspace.runner().run("container", "--health")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["severity"] == "ERROR"
        assert result.json["content"]["healthy"] is False
        checks: Dict[str, bool] = {
            check["identifier"]: check["passed"]
            for check in result.json["content"]["checks"]
        }
        assert checks["container_manifest_synced"] is False
        assert workspace.snapshot() == before

    def test_health_requires_a_container(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run("container", "--health")

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    def test_health_rejects_a_selector_without_a_value(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        result: CliInvocationResult = cli_runner.run(
            "container", "--container", "--health"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
