"""Installed CLI routing for `container --reconcile`: it tells what is missing and records the current state."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


class TestOntobdcContainerReconcileCommand:
    @pytest.mark.parametrize(
        "args",
        [("--reconcile", "extra"), ("--reconcile", "--container"), ("--reconcile", "--unknown", "x")],
    )
    def test_invalid_route_does_not_reconcile(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path, args: Tuple[str, ...]
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        before: Dict[str, bytes] = workspace.snapshot()

        result = cli_runner.run("container", *args)

        assert result.exit_code != 0, result.stdout
        assert "File Reconciliation" not in result.stdout
        assert workspace.snapshot() == before

    def test_lists_the_missing_files_and_the_files_of_the_same_name(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        runner: OntobdcCliProcessRunner = workspace.runner()
        (workspace.container / "docs").mkdir()
        (workspace.container / "docs" / "moved.png").write_text("a")
        (workspace.container / "docs" / "gone.pdf").write_text("b")
        assert runner.run("container", "--container", workspace.identifier, "--refresh").exit_code == 0

        (workspace.container / "docs" / "moved.png").rename(workspace.container / "moved.png")
        (workspace.container / "docs" / "gone.pdf").unlink()
        before: Dict[str, bytes] = workspace.snapshot()

        answer: Any = json.loads(
            runner.run("container", "--container", workspace.identifier, "--reconcile").stdout
        )

        by_path: Dict[str, Any] = {entry["path"]: entry for entry in answer["content"]["missing"]}
        assert sorted(by_path) == ["docs/gone.pdf", "docs/moved.png"]
        assert [other["path"] for other in by_path["docs/moved.png"]["same_name"]] == ["moved.png"]
        assert by_path["docs/gone.pdf"]["same_name"] == []

        # The files are not touched; only the crate has more.
        after: Dict[str, bytes] = workspace.snapshot()
        changed = sorted(path for path in after if after[path] != before.get(path))
        assert [path for path in changed if not path.endswith("ro-crate-metadata.json")] == []

    def test_records_the_current_state_of_a_file_that_changed_since_the_refresh(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        runner: OntobdcCliProcessRunner = workspace.runner()
        (workspace.container / "note.txt").write_text("one")
        assert runner.run("container", "--container", workspace.identifier, "--refresh").exit_code == 0

        (workspace.container / "note.txt").write_text("two, longer")
        os.utime(workspace.container / "note.txt", (1_900_000_000, 1_900_000_000))
        answer: Any = json.loads(
            runner.run("container", "--container", workspace.identifier, "--reconcile").stdout
        )

        assert answer["content"]["recorded"] == 1
        document: Any = json.loads((workspace.container / ".__ontobdc__" / "ro-crate-metadata.json").read_text(encoding="utf-8"))
        node: Any = next(item for item in document["@graph"] if item.get("name") == "note.txt")
        assert len(node["fileHistory"]) == 2
        assert node["fileHistory"][0]["sha256"] != node["fileHistory"][1]["sha256"]

    def test_names_the_files_by_identifiers_and_keeps_them_and_the_history_of_the_container_across_a_refresh(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        runner: OntobdcCliProcessRunner = workspace.runner()
        (workspace.container / "keep.txt").write_text("keep")
        (workspace.container / "gone.txt").write_text("gone")
        assert runner.run("container", "--container", workspace.identifier, "--refresh").exit_code == 0
        assert runner.run("container", "--container", workspace.identifier, "--reconcile").exit_code == 0

        def crate() -> Any:
            return json.loads((workspace.container / ".__ontobdc__" / "ro-crate-metadata.json").read_text(encoding="utf-8"))

        first = crate()
        parts = [part["@id"] for part in first["@graph"][0]["hasPart"]]
        assert all(len(identifier) == 36 for identifier in parts)
        identifier_of = {item["fileHistory"][-1]["relativePath"]: item["@id"] for item in first["@graph"] if item.get("@type") == "File"}

        (workspace.container / "gone.txt").unlink()
        assert runner.run("container", "--container", workspace.identifier, "--refresh").exit_code == 0

        second = crate()
        nodes = {item["fileHistory"][-1]["relativePath"]: item["@id"] for item in second["@graph"] if item.get("@type") == "File"}
        assert nodes == {"keep.txt": identifier_of["keep.txt"]}
        listed = {(entry["fileId"], entry["relativePath"]) for entry in second["@graph"][0]["fileHistory"]}
        assert (identifier_of["gone.txt"], "gone.txt") in listed


class TestOntobdcContainerReconcileMovedFiles:
    def _crate(self, workspace: ContainerE2eWorkspace) -> Any:
        return json.loads((workspace.container / ".__ontobdc__" / "ro-crate-metadata.json").read_text(encoding="utf-8"))

    def _reconcile(self, workspace: ContainerE2eWorkspace) -> Any:
        return json.loads(workspace.runner().run("container", "--container", workspace.identifier, "--reconcile").stdout)["content"]

    def _refresh(self, workspace: ContainerE2eWorkspace) -> None:
        assert workspace.runner().run("container", "--container", workspace.identifier, "--refresh").exit_code == 0

    def _node(self, workspace: ContainerE2eWorkspace, name: str) -> Any:
        return next(item for item in self._crate(workspace)["@graph"] if item.get("name") == name)

    def test_finds_again_by_content_a_file_that_moved_and_was_renamed(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "docs").mkdir()
        (workspace.container / "docs" / "plan.txt").write_text("the plan")
        (workspace.container / "docs" / "other.txt").write_text("another one")
        self._refresh(workspace)

        (workspace.container / "archive").mkdir()
        (workspace.container / "docs" / "plan.txt").rename(workspace.container / "archive" / "plan-final.txt")
        content = self._reconcile(workspace)

        assert [(item["from"], item["to"]) for item in content["relocated"]] == [("docs/plan.txt", "archive/plan-final.txt")]
        node: Any = self._node(workspace, "plan.txt")
        # The file keeps its one node; the old path is ended, and kept as it was.
        assert [(entry["relativePath"], "missingSince" in entry) for entry in node["fileHistory"]] == [
            ("docs/plan.txt", False), ("archive/plan-final.txt", False), ("docs/plan.txt", True),
        ]
        assert node["fileHistory"][1]["contentSize"] == len("the plan")
        assert sum(1 for item in self._crate(workspace)["@graph"] if item.get("@type") == "File" and "plan" in str(item.get("fileHistory"))) == 1
        assert content["orphans"] == []

    def test_a_file_moved_after_a_refresh_is_identified_by_the_history_of_the_container(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "plan.txt").write_text("the plan")
        self._refresh(workspace)
        self._reconcile(workspace)
        identifier: str = self._node(workspace, "plan.txt")["@id"]

        # The refresh drops the node of the file that is not there, and makes another for the new path.
        (workspace.container / "plan.txt").rename(workspace.container / "moved.txt")
        self._refresh(workspace)
        content = self._reconcile(workspace)

        assert [(item["from"], item["to"]) for item in content["relocated"]] == [("plan.txt", "moved.txt")]
        node: Any = self._node(workspace, "moved.txt")
        assert node["@id"] == identifier
        assert [entry["relativePath"] for entry in node["fileHistory"]][:2] == ["plan.txt", "moved.txt"]

    def test_a_copy_is_the_same_file_at_one_more_path(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        from ontobdc.storage.adapter.crate import ContainerRoCrate

        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "a.txt").write_text("same")
        self._refresh(workspace)
        self._reconcile(workspace)
        identifier: str = self._node(workspace, "a.txt")["@id"]

        (workspace.container / "b.txt").write_text("same")
        content = self._reconcile(workspace)

        assert [(item["from"], item["to"]) for item in content["relocated"]] == [("a.txt", "b.txt")]
        assert ContainerRoCrate.file_paths(workspace.container) == ["a.txt", "b.txt"]
        assert sum(1 for item in self._crate(workspace)["@graph"] if item.get("@id") == identifier) == 1
        # A refresh keeps one node for the file at its two paths.
        self._refresh(workspace)
        assert ContainerRoCrate.file_paths(workspace.container) == ["a.txt", "b.txt"]
        assert sum(1 for item in self._crate(workspace)["@graph"] if item.get("@id") == identifier) == 1

    def test_finds_again_by_name_and_size_a_file_that_moved_and_changed_its_content(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "docs").mkdir()
        (workspace.container / "docs" / "plan.txt").write_text("version 1")
        self._refresh(workspace)

        (workspace.container / "archive").mkdir()
        (workspace.container / "docs" / "plan.txt").unlink()
        (workspace.container / "archive" / "plan.txt").write_text("version 2")
        content = self._reconcile(workspace)

        assert content["relocated"] == []
        assert [(item["from"], item["to"]) for item in content["relocated_by_name_and_size"]] == [("docs/plan.txt", "archive/plan.txt")]
        node: Any = self._node(workspace, "plan.txt")
        live = [entry for entry in node["fileHistory"] if "missingSince" not in entry]
        assert live[-1]["relativePath"] == "archive/plan.txt"
        assert live[-1]["sha256"] != live[0]["sha256"]

    def test_leaves_alone_a_file_with_two_candidates_of_the_same_name_and_size(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "plan.txt").write_text("version 1")
        self._refresh(workspace)

        (workspace.container / "plan.txt").unlink()
        for folder in ("x", "y"):
            (workspace.container / folder).mkdir()
            (workspace.container / folder / "plan.txt").write_text("version 2")
        content = self._reconcile(workspace)

        assert content["relocated_by_name_and_size"] == []
        assert [item["path"] for item in content["orphans"]] == ["plan.txt"]

    def test_a_content_held_by_two_files_is_ambiguous_unless_the_name_tells(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "a.txt").write_text("same")
        (workspace.container / "b.txt").write_text("same")
        self._refresh(workspace)
        self._reconcile(workspace)

        (workspace.container / "a.txt").unlink()
        (workspace.container / "b.txt").unlink()
        (workspace.container / "c.txt").write_text("same")
        (workspace.container / "sub").mkdir()
        (workspace.container / "sub" / "a.txt").write_text("same")
        content = self._reconcile(workspace)

        # sub/a.txt is the file that was named so; c.txt could be either.
        assert [(item["from"], item["to"]) for item in content["relocated"]] == [("a.txt", "sub/a.txt")]
        assert [item["path"] for item in content["ambiguous"]] == ["c.txt"]

    def test_an_orphan_pointer_is_recorded_and_pointed_again_when_the_file_turns_up(
        self, cli_runner: OntobdcCliProcessRunner, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
        (workspace.container / "a.txt").write_text("keep me")
        self._refresh(workspace)
        self._reconcile(workspace)
        identifier: str = self._node(workspace, "a.txt")["@id"]

        (workspace.container / "a.txt").rename(workspace.container / "elsewhere.bin")
        (workspace.container / "elsewhere.bin").write_text("something else entirely")
        content = self._reconcile(workspace)

        assert content["orphans"] == [{"id": identifier, "path": "a.txt"}]
        node: Any = self._node(workspace, "a.txt")
        ending = node["fileHistory"][-1]
        assert ending["relativePath"] == "a.txt" and "missingSince" in ending
        assert ending["sha256"] == node["fileHistory"][0]["sha256"] and ending["contentSize"] == len("keep me")

        (workspace.container / "back.txt").write_text("keep me")
        content = self._reconcile(workspace)

        assert [(item["from"], item["to"]) for item in content["relocated"]] == [("a.txt", "back.txt")]
        assert content["orphans"] == []
