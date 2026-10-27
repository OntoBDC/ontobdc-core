from pathlib import Path
from typing import List

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository

SOURCE = Path(__file__).resolve().parents[2] / "src" / "ontobdc"


def test_lists_the_files_the_container_publishes(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "index.html").write_text("<html/>")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "x.txt").write_text("x")
    (tmp_path / "Thumbs.db").write_text("blocked")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "linkset").mkdir()
    (tmp_path / "sub" / "linkset" / "datapackage.json").write_text("{}")
    (tmp_path / "sub" / "own.txt").write_text("belongs to a dataset")

    assert ContainerFileRepository(tmp_path).list() == ["b.txt", "docs/a.txt"]


def test_tells_what_a_file_is_now(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    files = ContainerFileRepository(tmp_path)

    assert files.is_file("a.txt") and not files.is_file("missing.txt")
    assert files.size("a.txt") == 5 and files.size("missing.txt") is None
    assert files.sha256("a.txt") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    entry = files.entry("a.txt")
    assert entry is not None and (entry.relative_path, entry.size) == ("a.txt", 5)
    assert files.entry("missing.txt") is None


def test_the_files_of_the_container_are_only_looked_at_through_the_repository() -> None:
    """Nothing else walks the directory, hashes a file or stats it: what a path means is decided in one place."""
    users: List[Path] = [
        SOURCE / "storage" / "adapter" / "crate_file_history.py",
        SOURCE / "storage" / "adapter" / "file_ledger.py",
        SOURCE / "container" / "plugin" / "check" / "is_container_manifest_synced" / "check.py",
        SOURCE / "container" / "plugin" / "check" / "is_container_manifest_synced" / "hotfix.py",
        *sorted((SOURCE / "storage" / "plugin" / "capability" / "transformation").glob("*.py")),
    ]
    forbidden = ("os.walk", "hashlib", "safe_stat", "iterdir")
    offenders = [
        f"{path.relative_to(SOURCE)}: {word}"
        for path in users
        if path.name not in {"path_normalized.py", "path_language_identified.py", "path_lemmatized.py", "file_metadata_extracted.py", "single_file_metadata_extracted.py", "file_opening_strategy_found.py"}
        for word in forbidden
        if word in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
