from typing import Any, ClassVar, Dict, List, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcRunCapabilityCommand:
    HEALTH_CAPABILITY: ClassVar[str] = (
        "org.ontobdc.container.plugin.capability.health.container_health"
    )
    MANIFEST_CAPABILITY: ClassVar[str] = (
        "org.ontobdc.container.plugin.capability.transformation.target.container_manifest_synced"
    )

    @pytest.mark.parametrize("selector", ["cwd", "id", "path"])
    def test_run_executes_a_real_health_capability_with_the_selected_container(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        selector: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()
        result: CliInvocationResult
        if selector == "cwd":
            result = workspace.runner().run(
                "run", "--capability", self.HEALTH_CAPABILITY
            )
        else:
            result = cli_runner.run(
                "run",
                "--capability",
                self.HEALTH_CAPABILITY,
                "--container",
                workspace.selector(selector),
            )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert result.json["content"]["capability_id"] == self.HEALTH_CAPABILITY
        report: Dict[str, Any] = result.json["content"]["result"]
        assert report["healthy"] is True
        checks: List[Dict[str, Any]] = report["checks"]
        assert checks
        assert all(check["passed"] is True for check in checks)
        assert workspace.snapshot() == before

    def test_run_executes_a_real_manifest_transformation(self, tmp_path: Path) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        user_file: Path = workspace.container / "new.txt"
        user_file.write_text("New resource", encoding="utf-8")
        assert "new.txt" not in workspace.manifest_files()

        result: CliInvocationResult = workspace.runner().run(
            "run", "--capability", self.MANIFEST_CAPABILITY
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "OntoBDC Run"
        assert result.json["content"]["capability_id"] == self.MANIFEST_CAPABILITY
        assert (
            Path(result.json["content"]["result"]["container_path"]).resolve()
            == workspace.container
        )
        assert "new.txt" in workspace.manifest_files()
        assert user_file.read_text(encoding="utf-8") == "New resource"

    def test_run_rejects_an_unknown_capability(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0
        missing: str = "org.ontobdc.e2e.nonexistent_capability"

        result: CliInvocationResult = cli_runner.run("run", "--capability", missing)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
        assert missing in result.json["content"]["error"].replace("\n", "")

    def test_run_rejects_a_missing_required_container(
        self, cli_runner: OntobdcCliProcessRunner
    ) -> None:
        assert cli_runner.run("init").exit_code == 0

        result: CliInvocationResult = cli_runner.run(
            "run", "--capability", self.HEALTH_CAPABILITY
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--capability",),
            ("--capability", ""),
            ("--capability", "   "),
            ("--capability", "id", "--container"),
            ("--capability", "id", "extra"),
        ],
    )
    def test_run_rejects_missing_or_extra_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("run", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
