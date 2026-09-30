from typing import Any, Dict, List, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerAttachCommand:
    @pytest.mark.parametrize("selector", ["cwd", "--container-path", "--container"])
    def test_attach_imports_a_moved_container_preserving_identity_and_user_files(
        self,
        tmp_path: Path,
        selector: str,
    ) -> None:
        source_root: Path = tmp_path / "origin"
        source_root.mkdir()
        source: ContainerE2eWorkspace = ContainerE2eWorkspace.create(source_root)
        (source.container / "measurements.csv").write_text(
            "value\n42\n", encoding="utf-8"
        )
        target_root: Path = tmp_path / "destination"
        target_root.mkdir()
        target_runner: OntobdcCliProcessRunner = OntobdcCliProcessRunner(target_root)
        assert target_runner.run("init").exit_code == 0
        imported: Path = target_root / "imported"
        source.container.rename(imported)
        runner: OntobdcCliProcessRunner
        arguments: Tuple[str, ...]
        if selector == "cwd":
            runner = OntobdcCliProcessRunner(imported)
            arguments = ("container", "--attach")
        else:
            runner = target_runner
            arguments = ("container", selector, str(imported), "--attach")

        result: CliInvocationResult = runner.run(*arguments)

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Storage Container Attached"
        assert (
            result.json["content"]["current_state"] == "__container_ro_crate_updated__"
        )
        assert (
            Path(result.json["content"]["container_path"]).resolve()
            == imported.resolve()
        )
        listing: CliInvocationResult = target_runner.run("container")
        assert listing.exit_code == 0, listing.stdout
        entries: List[Dict[str, Any]] = listing.json["content"]["containers"]
        assert len(entries) == 1
        assert entries[0]["id"] == source.identifier
        assert Path(entries[0]["location"]).resolve() == imported.resolve()
        assert (imported / "measurements.csv").read_bytes() == b"value\n42\n"
        imported_workspace: ContainerE2eWorkspace = ContainerE2eWorkspace(
            target_root, imported, source.identifier
        )
        assert "measurements.csv" in imported_workspace.manifest_files()

        repeated: CliInvocationResult = runner.run(*arguments)
        assert repeated.exit_code == 0, repeated.stdout + repeated.stderr
        assert repeated.json["title"] == "Storage Container Attached"
        repeated_listing: CliInvocationResult = target_runner.run("container")
        assert repeated_listing.exit_code == 0, repeated_listing.stdout
        assert [
            entry["id"] for entry in repeated_listing.json["content"]["containers"]
        ] == [source.identifier]
        assert (imported / "measurements.csv").read_bytes() == b"value\n42\n"

    def test_attach_rejects_a_nonexistent_directory(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
    ) -> None:
        assert cli_runner.run("init").exit_code == 0
        missing: Path = tmp_path / "missing"

        result: CliInvocationResult = cli_runner.run(
            "container", "--container-path", str(missing), "--attach"
        )

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
        assert not missing.exists()

    @pytest.mark.parametrize(
        "arguments",
        [
            ("--attach", "--attach"),
            ("--container-path", "--attach"),
            ("--container-path", "", "--attach"),
        ],
    )
    def test_attach_rejects_duplicate_flags_and_missing_paths(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
