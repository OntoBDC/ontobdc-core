from typing import Any, Dict, List, Tuple
from pathlib import Path

import pytest

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerDeleteCommand:
    @pytest.mark.parametrize("identifier_form", ["urn", "uuid"])
    def test_delete_unregisters_only_the_selected_container_and_preserves_files(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        identifier_form: str,
    ) -> None:
        target: ContainerE2eWorkspace = ContainerE2eWorkspace.create(
            tmp_path, "selected"
        )
        other: ContainerE2eWorkspace = ContainerE2eWorkspace.create(
            tmp_path, "preserved"
        )
        (target.container / "measurements.csv").write_text(
            "value\n10\n", encoding="utf-8"
        )
        before: Dict[str, bytes] = target.snapshot()
        other_before: Dict[str, bytes] = other.snapshot()

        identifier: str = target.identifier
        if identifier_form == "uuid":
            identifier = identifier.removeprefix("urn:uuid:")
        result: CliInvocationResult = cli_runner.run(
            "container", "--delete", identifier
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Container Unregistered"
        assert result.json["content"]["container_id"] == target.identifier
        listing: CliInvocationResult = cli_runner.run("container")
        assert listing.exit_code == 0, listing.stdout
        entries: List[Dict[str, Any]] = listing.json["content"]["containers"]
        assert [entry["id"] for entry in entries] == [other.identifier]
        assert target.snapshot() == before
        assert other.snapshot() == other_before

    @pytest.mark.parametrize(
        "identifier, error",
        [
            ("urn:uuid:00000000-0000-4000-8000-000000000001", "not registered"),
            ("", "Container id cannot be empty."),
            ("   ", "Container id cannot be empty."),
        ],
    )
    def test_delete_reports_unknown_or_empty_identifiers_without_changing_storage(
        self,
        cli_runner: OntobdcCliProcessRunner,
        tmp_path: Path,
        identifier: str,
        error: str,
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        storage: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        before: bytes = storage.read_bytes()

        result: CliInvocationResult = cli_runner.run(
            "container", "--delete", identifier
        )

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["title"] == "Failed to Unregister Container"
        assert error in result.json["content"]["error"]
        assert storage.read_bytes() == before

    @pytest.mark.parametrize("arguments", [("--delete",), ("--delete", "id", "extra")])
    def test_delete_rejects_invalid_arguments(
        self,
        cli_runner: OntobdcCliProcessRunner,
        arguments: Tuple[str, ...],
    ) -> None:
        result: CliInvocationResult = cli_runner.run("container", *arguments)

        assert result.exit_code == 1, result.stdout
        assert result.json["title"] == "Run Exception"
