"""The refresh keeps the history of each file in its node of the RO-Crate."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from test.e2e.cli_process_runner import OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


def history_of(workspace: ContainerE2eWorkspace, relative_path: str) -> List[Dict[str, Any]]:
    document: Any = json.loads((workspace.container / ".__ontobdc__" / "ro-crate-metadata.json").read_text(encoding="utf-8"))
    node: Any = next(item for item in document["@graph"] if item["@id"] == relative_path)
    return node["fileHistory"]


def refresh(workspace: ContainerE2eWorkspace) -> None:
    assert workspace.runner().run("container", "--container", workspace.identifier, "--refresh").exit_code == 0


def test_the_node_of_a_file_carries_its_path_hash_and_timestamp(
    cli_runner: OntobdcCliProcessRunner, tmp_path: Path
) -> None:
    workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
    (workspace.container / "docs").mkdir()
    (workspace.container / "docs" / "plan.txt").write_text("the plan")
    refresh(workspace)

    history = history_of(workspace, "docs/plan.txt")

    assert len(history) == 1
    assert history[0]["relativePath"] == "docs/plan.txt"
    assert len(history[0]["sha256"]) == 64 and history[0]["timestamp"].endswith("Z")


def test_a_file_that_is_not_touched_keeps_its_one_entry_and_a_changed_one_gets_another(
    cli_runner: OntobdcCliProcessRunner, tmp_path: Path
) -> None:
    workspace: ContainerE2eWorkspace = ContainerE2eWorkspace.create(tmp_path)
    (workspace.container / "still.txt").write_text("same")
    (workspace.container / "note.txt").write_text("one")
    refresh(workspace)

    (workspace.container / "note.txt").write_text("two, longer")
    os.utime(workspace.container / "note.txt", (1_900_000_000, 1_900_000_000))
    refresh(workspace)

    assert len(history_of(workspace, "still.txt")) == 1
    note = history_of(workspace, "note.txt")
    assert len(note) == 2 and note[0]["sha256"] != note[1]["sha256"]
    assert [entry["timestamp"] for entry in note] == sorted(entry["timestamp"] for entry in note)
