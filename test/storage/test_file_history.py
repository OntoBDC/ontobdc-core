import json
import os
from pathlib import Path

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import DatasetHistoryEntry, FileHistory, FileHistoryEntry


def entry(path: str, sha: str, timestamp: str) -> FileHistoryEntry:
    return FileHistoryEntry(path, sha, timestamp)


def test_the_history_is_one_list_ordered_by_timestamp_whatever_order_entries_come_in() -> None:
    history = FileHistory([
        entry("b.txt", "2", "2026-02-01T00:00:00Z"),
        entry("a.txt", "1", "2026-01-01T00:00:00Z"),
        entry("a.txt", "1", "2026-01-01T00:00:00Z"),
        entry("c.txt", "3", "2026-01-01T00:00:00Z"),
    ])

    assert [(item.relative_path, item.timestamp) for item in history] == [
        ("a.txt", "2026-01-01T00:00:00Z"),
        ("c.txt", "2026-01-01T00:00:00Z"),
        ("b.txt", "2026-02-01T00:00:00Z"),
    ]


def test_the_history_knows_its_latest_entry_and_where_a_content_has_been() -> None:
    history = FileHistory([
        entry("docs/a.txt", "new", "2026-02-01T00:00:00Z"),
        entry("a.txt", "old", "2026-01-01T00:00:00Z"),
        entry("a.txt", "new", "2026-03-01T00:00:00Z"),
    ])

    latest = history.latest()
    assert latest is not None and (latest.relative_path, latest.sha256) == ("a.txt", "new")
    assert FileHistory().latest() is None
    assert sorted(item.relative_path for item in history.with_content("new")) == ["a.txt", "docs/a.txt"]


def test_with_entries_does_not_change_the_history_it_is_called_on() -> None:
    history = FileHistory([entry("a.txt", "1", "2026-01-01T00:00:00Z")])

    longer = history.with_entries([entry("b.txt", "2", "2026-01-02T00:00:00Z")])

    assert (len(history), len(longer)) == (1, 2)


def test_the_entry_of_a_file_hashes_it_only_when_it_changed(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")

    first = CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", FileHistory())
    assert first is not None
    assert first.sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    # What an entry with the very path and timestamp says is taken as true: the file is not read again.
    trusting = FileHistory([FileHistoryEntry("a.txt", "whatever", first.timestamp)])
    assert CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", trusting) == FileHistoryEntry("a.txt", "whatever", first.timestamp, 5)

    os.utime(tmp_path / "a.txt", (1_700_000_000, 1_700_000_000))
    again = CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", trusting)
    assert again is not None and again.sha256 == first.sha256 and again.timestamp != first.timestamp


def test_the_history_of_a_file_keeps_what_it_had_and_adds_what_it_is_now(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("one")
    first = CrateFileHistory.history_of(ContainerFileRepository(tmp_path), "a.txt", FileHistory())
    assert len(first) == 1

    assert CrateFileHistory.history_of(ContainerFileRepository(tmp_path), "a.txt", first) == first

    (tmp_path / "a.txt").write_text("two, longer")
    os.utime(tmp_path / "a.txt", (1_800_000_000, 1_800_000_000))
    second = CrateFileHistory.history_of(ContainerFileRepository(tmp_path), "a.txt", first)
    assert len(second) == 2 and second.entries[0] == first.entries[0]
    assert second.entries[0].sha256 != second.entries[1].sha256


def test_the_node_of_a_file_carries_its_history_in_one_ordered_list_and_it_reads_back(tmp_path: Path) -> None:
    document = {
        "@context": "https://w3id.org/ro/crate/1.3/context",
        "@graph": [
            {"@id": "./", "@type": "Dataset", "hasPart": [{"@id": "a.txt"}]},
            {"@id": "a.txt", "@type": "File", "name": "a.txt"},
        ],
    }
    crate_file = tmp_path / "ro-crate-metadata.json"
    crate_file.write_text(json.dumps(document), encoding="utf-8")
    history = FileHistory([
        entry("a.txt", "2", "2026-02-01T00:00:00Z"),
        entry("old/a.txt", "1", "2026-01-01T00:00:00Z"),
    ])

    CrateFileHistory.save(crate_file, {"a.txt": history, "not-stated.txt": history})

    saved = json.loads(crate_file.read_text(encoding="utf-8"))
    node = next(item for item in saved["@graph"] if item["@id"] == "a.txt")
    assert [item["relativePath"] for item in node["fileHistory"]] == ["old/a.txt", "a.txt"]
    assert set(node["fileHistory"][0]) == {"relativePath", "sha256", "timestamp"}
    assert all("fileHistory" not in item for item in saved["@graph"] if item["@id"] != "a.txt")
    assert "fileHistory" in saved["@context"][1]
    assert CrateFileHistory.read(saved) == {"a.txt": history}


def crate_with_files() -> dict:
    return {
        "@context": "https://w3id.org/ro/crate/1.3/context",
        "@graph": [
            {"@id": "./", "@type": "Dataset", "hasPart": [{"@id": "a.txt"}, {"@id": "nohistory.txt"}]},
            {
                "@id": "a.txt",
                "@type": "File",
                "fileHistory": [
                    {"relativePath": "old/a.txt", "sha256": "1", "timestamp": "2026-01-01T00:00:00Z"},
                    {"relativePath": "a.txt", "sha256": "1", "timestamp": "2026-02-01T00:00:00Z"},
                ],
            },
            {"@id": "nohistory.txt", "@type": "File"},
        ],
    }


def test_a_file_is_named_by_an_identifier_and_its_path_stays_in_its_history() -> None:
    document = crate_with_files()

    given, left = CrateFileHistory.replace_identifiers(document)

    identifier = given["a.txt"]
    assert CrateFileHistory.is_identifier(identifier)
    assert left == ["nohistory.txt"]
    assert [part["@id"] for part in document["@graph"][0]["hasPart"]] == [identifier, "nohistory.txt"]
    node = next(item for item in document["@graph"] if item["@id"] == identifier)
    assert CrateFileHistory.path_of(node) == "a.txt"
    assert CrateFileHistory.replace_identifiers(document) == ({}, ["nohistory.txt"])


def test_the_history_of_the_dataset_has_the_entries_of_every_file_with_its_identifier_and_keeps_the_gone_ones() -> None:
    document = crate_with_files()
    given, _ = CrateFileHistory.replace_identifiers(document)
    gone = DatasetHistoryEntry("some-gone-file", "gone.txt", "9", "2025-12-01T00:00:00Z")
    CrateFileHistory.set_dataset_entries(document, [gone])

    CrateFileHistory.set_dataset_entries(document, CrateFileHistory.dataset_entries_of(document))

    listed = document["@graph"][0]["fileHistory"]
    assert [item["relativePath"] for item in listed] == ["gone.txt", "old/a.txt", "a.txt"]
    assert listed[1]["fileId"] == given["a.txt"] and set(listed[1]) == {"fileId", "relativePath", "sha256", "timestamp"}
    assert CrateFileHistory.read_dataset_entries(document)[0] == gone


def test_an_entry_keeps_the_size_and_one_that_lacks_it_gives_way_to_the_same_moment_with_it() -> None:
    old = FileHistoryEntry("a.txt", "1", "2026-01-01T00:00:00Z")
    sized = FileHistoryEntry("a.txt", "1", "2026-01-01T00:00:00Z", 5)

    assert list(FileHistory([old, sized])) == [sized]
    assert list(FileHistory([old])) == [old]


def test_the_size_is_written_in_the_crate_and_read_back(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    now = CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", FileHistory())
    assert now is not None and now.size == 5

    [item] = CrateFileHistory.value_of(FileHistory([now]))
    assert item["contentSize"] == 5
    crate = {"@graph": [{"@id": "a.txt", "@type": "File", "fileHistory": [item]}]}
    assert CrateFileHistory.read(crate)["a.txt"].latest() == now


def test_an_entry_written_before_the_size_learns_it_without_reading_the_content_again(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    first = CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", FileHistory())
    assert first is not None
    trusting = FileHistory([FileHistoryEntry("a.txt", "whatever", first.timestamp)])

    assert CrateFileHistory.entry_of(ContainerFileRepository(tmp_path), "a.txt", trusting) == FileHistoryEntry("a.txt", "whatever", first.timestamp, 5)


def test_entries_of_the_same_moment_stay_in_the_order_they_were_added_in_so_a_move_is_the_latest() -> None:
    before = FileHistory([FileHistoryEntry("docs/a.txt", "1", "2026-01-01T00:00:00Z", 3)])

    after = before.with_entries([FileHistoryEntry("archive/a.txt", "1", "2026-01-01T00:00:00Z", 3)])

    assert after.latest().relative_path == "archive/a.txt"
