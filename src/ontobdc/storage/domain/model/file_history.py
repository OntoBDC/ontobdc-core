from dataclasses import dataclass
from typing import Any, Iterable, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class FileHistoryEntry:
    """
    One time a file of a container was seen different: where it was, what it held and when.

    ``relative_path`` is the path of the file in the container, relative to its root;
    ``sha256`` the hash of its content, as lowercase hexadecimal; ``timestamp`` when it was last
    modified, in UTC (ISO 8601, ending in ``Z``), or when it was created when the system tells no
    modification time; ``size`` its size in bytes (None in an entry written before the size was
    kept); ``missing_since`` when the file was found no longer at that path (None for an entry
    that says the file is there). An entry that says the file is missing keeps the path, hash, size
    and timestamp of the entry it ends, so the path can be pointed again when the file turns up.
    """

    relative_path: str
    sha256: str
    timestamp: str
    size: Optional[int] = None
    missing_since: Optional[str] = None

    def sort_key(self) -> str:
        return self.timestamp

    def identity(self) -> Tuple[str, str, str, Optional[str]]:
        """What makes an entry the same moment of the same file, whether or not it knows the size."""
        return (self.relative_path, self.sha256, self.timestamp, self.missing_since)

    def ended(self, missing_since: str) -> "FileHistoryEntry":
        """The entry that says the file is no longer at the path of this one."""
        return FileHistoryEntry(self.relative_path, self.sha256, self.timestamp, self.size, missing_since)


def without_superseded(entries: Iterable[Any]) -> List[Any]:
    """
    The entries once each (the first of an entry that comes twice stays), an entry that does not
    know its size left out when another says the same (path, hash, timestamp) with it. Works for
    the entries of a file and of the container.
    """
    unique: List[Any] = list(dict.fromkeys(entries))
    sized = {(getattr(entry, "file_id", None), entry.identity()) for entry in unique if entry.size is not None}
    return [
        entry for entry in unique
        if entry.size is not None or (getattr(entry, "file_id", None), entry.identity()) not in sized
    ]


class FileHistory:
    """
    The history of one file of a container: its entries, once each, in one list ordered by
    timestamp, the oldest first. An entry says where the file was, so the path of the entries may
    differ when the file has moved. Entries of the same moment (a move does not change the time a
    file was modified) stay in the order they were added in, so the latest is the one added last.

    A file can be at several paths at once (a copy is the same file). Each path is live while the
    last entry that names it does not say the file is missing.
    """

    def __init__(self, entries: Iterable[FileHistoryEntry] = ()) -> None:
        self._entries: Tuple[FileHistoryEntry, ...] = tuple(
            sorted(without_superseded(entries), key=FileHistoryEntry.sort_key)
        )

    @property
    def entries(self) -> Tuple[FileHistoryEntry, ...]:
        return self._entries

    def __iter__(self) -> Iterator[FileHistoryEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FileHistory) and self._entries == other._entries

    def with_entries(self, entries: Iterable[FileHistoryEntry]) -> "FileHistory":
        """
        A history with these entries as well; the one that is called is not changed. An entry the
        history has already stays where it is, unless the path it names was ended since: then the
        file is there again and the entry is the latest.
        """
        items: List[FileHistoryEntry] = list(self._entries)
        for entry in entries:
            last: Optional[FileHistoryEntry] = FileHistory(items).last_at(entry.relative_path)
            if entry in items and last is not None and last.missing_since is not None and entry.missing_since is None:
                items.remove(entry)
            items.append(entry)
        return FileHistory(items)

    def last_at(self, relative_path: str) -> Optional[FileHistoryEntry]:
        """The most recent entry that names the path, an entry that ends it included."""
        found: Optional[FileHistoryEntry] = None
        for entry in self._entries:
            if entry.relative_path == relative_path:
                found = entry
        return found

    def live_entries(self) -> List[FileHistoryEntry]:
        """The last entry of each path the file is still at, in the order of the history."""
        last: dict = {entry.relative_path: index for index, entry in enumerate(self._entries)}
        return [
            entry for index, entry in enumerate(self._entries)
            if last[entry.relative_path] == index and entry.missing_since is None
        ]

    def current(self) -> Optional[FileHistoryEntry]:
        """
        Where the file is: the most recent entry of a path it is still at. A file that is nowhere (an
        orphan) is where it was last seen: the latest entry.
        """
        live: List[FileHistoryEntry] = self.live_entries()
        return live[-1] if live else self.latest()

    def live_paths(self) -> List[str]:
        """The paths the file is at, the current one first, the others in the order of the history."""
        paths: List[str] = [entry.relative_path for entry in reversed(self.live_entries())]
        return paths

    def is_orphan(self) -> bool:
        """Whether the history has entries and the file is at none of its paths."""
        return len(self._entries) > 0 and not self.live_entries()

    def latest(self) -> Optional[FileHistoryEntry]:
        """The most recent entry, or None when the history is empty."""
        return self._entries[-1] if self._entries else None

    def with_content(self, sha256: str) -> List[FileHistoryEntry]:
        """The entries in which the file held that content, wherever it was."""
        return [entry for entry in self._entries if entry.sha256 == sha256]


@dataclass(frozen=True)
class DatasetHistoryEntry:
    """
    An entry of the history of the whole container: the entry of a file, and the identifier of the
    file it is of. The identifier is what ties the entries of a file together when it moves, and
    so changes its path.
    """

    file_id: str
    relative_path: str
    sha256: str
    timestamp: str
    size: Optional[int] = None
    missing_since: Optional[str] = None

    def sort_key(self) -> str:
        return self.timestamp

    def identity(self) -> Tuple[str, str, str, Optional[str]]:
        return (self.relative_path, self.sha256, self.timestamp, self.missing_since)
