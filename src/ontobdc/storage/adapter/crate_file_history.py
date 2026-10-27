from datetime import datetime, timezone
import json
import re
import uuid
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_properties import CrateFileProperties
from ontobdc.storage.domain.model.file_history import DatasetHistoryEntry, FileHistory, FileHistoryEntry, without_superseded


class CrateFileHistory:
    """
    The history of a file as the RO-Crate keeps it: a property of the node of the file
    (``fileHistory``), one list ordered by timestamp, whose items carry the path, the hash and the
    timestamp of one entry (``relativePath``, ``sha256``, ``timestamp``, ``contentSize``). The terms are the ones of
    the core ontology of OntoBDC (``core/ns.ttl``), declared in the context of the crate.
    """

    LIST_PROPERTY: ClassVar[str] = "fileHistory"
    PATH_PROPERTY: ClassVar[str] = "relativePath"
    HASH_PROPERTY: ClassVar[str] = "sha256"
    TIME_PROPERTY: ClassVar[str] = "timestamp"
    SIZE_PROPERTY: ClassVar[str] = "contentSize"
    MISSING_PROPERTY: ClassVar[str] = "missingSince"
    FILE_ID_PROPERTY: ClassVar[str] = "fileId"
    ROOT_NODE_ID: ClassVar[str] = "./"
    IDENTIFIER_PATTERN: ClassVar["re.Pattern[str]"] = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    FILE_TYPE: ClassVar[str] = "File"

    # What each term of the crate stands for in the ontology.
    TERMS: ClassVar[Dict[str, str]] = {
        LIST_PROPERTY: str(CrateFileProperties.CORE.fileHistory),
        PATH_PROPERTY: str(CrateFileProperties.CORE.relativePath),
        HASH_PROPERTY: str(CrateFileProperties.CORE.sha256),
        TIME_PROPERTY: str(CrateFileProperties.CORE.historyTimestamp),
        FILE_ID_PROPERTY: str(CrateFileProperties.CORE.fileId),
        SIZE_PROPERTY: str(CrateFileProperties.CORE.historySize),
        MISSING_PROPERTY: str(CrateFileProperties.CORE.missingSince),
    }

    @classmethod
    def read(cls, crate_data: Any) -> Dict[str, FileHistory]:
        """
        The history of each file the crate document states, by the path of its node, in the order the
        crate states it. A file without history has none here; an item that lacks its path, hash or
        timestamp is not an entry and is left out.
        """
        graph: Any = crate_data.get("@graph") if isinstance(crate_data, dict) else None
        histories: Dict[str, FileHistory] = {}
        if not isinstance(graph, list):
            return histories

        for node in graph:
            if not isinstance(node, dict) or not cls._is_file(node):
                continue
            path: Optional[str] = cls.path_of(node)
            items: Any = node.get(cls.LIST_PROPERTY)
            if path is None or not isinstance(items, list):
                continue

            histories[path] = cls._history_of_items(items)

        return histories

    @classmethod
    def _history_of_items(cls, items: Any) -> FileHistory:
        """The history a list of items of a crate states; an item that is not an entry is left out."""
        entries: List[FileHistoryEntry] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            values: List[Any] = [item.get(cls.PATH_PROPERTY), item.get(cls.HASH_PROPERTY), item.get(cls.TIME_PROPERTY)]
            if all(isinstance(value, str) and value for value in values):
                missing: Any = item.get(cls.MISSING_PROPERTY)
                entries.append(FileHistoryEntry(*values, size=cls._size_of(item), missing_since=missing if isinstance(missing, str) and missing else None))
        return FileHistory(entries)

    @classmethod
    def entry_of(cls, files: ContainerFileRepository, relative_path: str, previous: FileHistory) -> Optional[FileHistoryEntry]:
        """
        The entry of a file as it is now: its path, the hash of its content and its timestamp. The
        content is read only when it may have changed: a file whose latest entry for that path has the
        very timestamp it has now is taken to hold what that entry says. None when the file cannot be
        read, which is only acceptable for one that vanished meanwhile.
        """
        timestamp: Optional[str] = files.modified(relative_path)
        if timestamp is None:
            return None

        size: Optional[int] = files.size(relative_path)
        known: Optional[FileHistoryEntry] = previous.last_at(relative_path)
        if known is not None and known.missing_since is None and known.timestamp == timestamp:
            # An entry written before the size was kept learns it; the content is not read again.
            return known if known.size is not None else FileHistoryEntry(relative_path, known.sha256, timestamp, size)
        return FileHistoryEntry(relative_path, files.sha256(relative_path), timestamp, size)

    @classmethod
    def history_of(cls, files: ContainerFileRepository, relative_path: str, previous: FileHistory) -> FileHistory:
        """
        The history of the file after looking at it as it is: what the history had, and an entry for
        what the file is now when that is not already its latest. Nothing the history had is taken out.
        """
        entry: Optional[FileHistoryEntry] = cls.entry_of(files, relative_path, previous)
        return previous if entry is None else previous.with_entries([entry])

    @classmethod
    def value_of(cls, history: FileHistory) -> List[Dict[str, str]]:
        """The history as the node of the file carries it: the list of its entries, in order."""
        return [cls._item_of(entry) for entry in history]

    @classmethod
    def _item_of(cls, entry: Any) -> Dict[str, Any]:
        item: Dict[str, Any] = {}
        if hasattr(entry, "file_id"):
            item[cls.FILE_ID_PROPERTY] = entry.file_id
        item[cls.PATH_PROPERTY] = entry.relative_path
        item[cls.HASH_PROPERTY] = entry.sha256
        item[cls.TIME_PROPERTY] = entry.timestamp
        if entry.size is not None:
            item[cls.SIZE_PROPERTY] = entry.size
        if entry.missing_since is not None:
            item[cls.MISSING_PROPERTY] = entry.missing_since
        return item

    @staticmethod
    def _size_of(item: Dict[str, Any]) -> Optional[int]:
        size: Any = item.get(CrateFileHistory.SIZE_PROPERTY)
        return size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None

    @classmethod
    def save(
        cls,
        crate_file: Path,
        histories: Dict[str, FileHistory],
        identifiers: Optional[Dict[str, str]] = None,
        dataset_entries: Optional[List[DatasetHistoryEntry]] = None,
    ) -> None:
        """
        Puts the history of each file in its node in the crate document that is there, and changes
        nothing else in it: the terms are declared in the context. A file the crate does not state is
        not given one. ``identifiers``, by path, gives the nodes their identifier back (a crate
        written again names its files by path); ``dataset_entries`` is the history of the whole
        container the root dataset keeps, which a crate written again would have lost.

        Raises:
            ValueError: the document is not an RO-Crate.
        """
        document: Any = json.loads(crate_file.read_text(encoding="utf-8"))
        graph: Any = document.get("@graph") if isinstance(document, dict) else None
        if not isinstance(graph, list):
            raise ValueError(f"{crate_file} is not an RO-Crate.")

        for node in graph:
            if not isinstance(node, dict) or not cls._is_file(node):
                continue
            path: Optional[str] = cls.path_of(node)
            if path is not None and path in histories:
                node[cls.LIST_PROPERTY] = cls.value_of(histories[path])
        if identifiers:
            cls.give_identifiers(document, identifiers)
        if dataset_entries:
            cls.set_dataset_entries(document, dataset_entries)

        cls.declare_terms(document)
        crate_file.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def is_identifier(cls, value: Any) -> bool:
        """Whether a crate id is the identifier of a file (a UUID) and not its path."""
        return isinstance(value, str) and cls.IDENTIFIER_PATTERN.match(value) is not None

    @classmethod
    def path_of(cls, node: Dict[str, Any]) -> Optional[str]:
        """
        The path of the file a node of the crate describes. A node named by its path says it; a node
        named by an identifier says it in its history: the path of its latest entry. None for a node
        that says neither.
        """
        node_id: Any = node.get("@id")
        if not isinstance(node_id, str) or not node_id.strip():
            return None
        if not cls.is_identifier(node_id):
            path: str = unquote(node_id.strip())
            return path[len(cls.ROOT_NODE_ID):] if path.startswith(cls.ROOT_NODE_ID) else path

        current: Optional[FileHistoryEntry] = cls._history_of_items(node.get(cls.LIST_PROPERTY)).current()
        return current.relative_path if current is not None else None

    @classmethod
    def paths_of(cls, node: Dict[str, Any]) -> List[str]:
        """
        Every path the file of a node is at, the current one first: a copy is the same file, so a file
        may be at several. A node named by its path is at that path, and at the other paths its history
        says it is still at.
        """
        primary: Optional[str] = cls.path_of(node)
        if primary is None:
            return []
        live: List[str] = cls._history_of_items(node.get(cls.LIST_PROPERTY)).live_paths()
        return [primary, *(path for path in live if path != primary)]

    @classmethod
    def read_identifiers(cls, crate_data: Any) -> Dict[str, str]:
        """The identifier of each file the crate names by one, by its path."""
        graph: Any = crate_data.get("@graph") if isinstance(crate_data, dict) else None
        found: Dict[str, str] = {}
        for node in graph if isinstance(graph, list) else []:
            if isinstance(node, dict) and cls._is_file(node) and cls.is_identifier(node.get("@id")):
                for path in cls.paths_of(node):
                    found[path] = node["@id"]
        return found

    @classmethod
    def read_all(cls, crate_data: Any) -> Dict[str, FileHistory]:
        """The history of the file at each path the crate document states, a file at several paths having its one history at each."""
        graph: Any = crate_data.get("@graph") if isinstance(crate_data, dict) else None
        found: Dict[str, FileHistory] = {}
        for node in graph if isinstance(graph, list) else []:
            if isinstance(node, dict) and cls._is_file(node):
                history: FileHistory = cls._history_of_items(node.get(cls.LIST_PROPERTY))
                for path in cls.paths_of(node):
                    found[path] = history
        return found

    @classmethod
    def owners(cls, document: Any) -> Dict[str, str]:
        """The id of the file node at each path the crate document states."""
        graph: Any = document.get("@graph") if isinstance(document, dict) else None
        found: Dict[str, str] = {}
        for node in graph if isinstance(graph, list) else []:
            if isinstance(node, dict) and cls._is_file(node) and isinstance(node.get("@id"), str):
                for path in cls.paths_of(node):
                    found.setdefault(path, node["@id"])
        return found

    @staticmethod
    def now() -> str:
        """The moment, in UTC, as an entry states it."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def end_missing(cls, history: FileHistory, present: Any, when: Optional[str] = None) -> FileHistory:
        """
        The history after saying the file is no longer at the paths it was at and are not in
        ``present``: each gets an entry that ends it, which keeps what the file was there.
        """
        moment: str = when or cls.now()
        return history.with_entries([entry.ended(moment) for entry in history.live_entries() if entry.relative_path not in present])

    @classmethod
    def node_histories(cls, document: Any) -> Dict[str, FileHistory]:
        """The history of each file node of the crate document, by the id of the node."""
        graph: Any = document.get("@graph") if isinstance(document, dict) else None
        return {
            node["@id"]: cls._history_of_items(node.get(cls.LIST_PROPERTY))
            for node in graph if isinstance(graph, list) and isinstance(node, dict) and cls._is_file(node) and isinstance(node.get("@id"), str)
        } if isinstance(graph, list) else {}

    @classmethod
    def set_node_history(cls, document: Dict[str, Any], node_id: str, history: FileHistory) -> None:
        """Puts a history in the node with this id."""
        for node in document["@graph"]:
            if isinstance(node, dict) and cls._is_file(node) and node.get("@id") == node_id:
                node[cls.LIST_PROPERTY] = cls.value_of(history)
                return
        raise ValueError(f"The RO-Crate has no file node {node_id}.")

    @classmethod
    def replace_identifiers(cls, document: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
        """
        Names each file of the crate document by an identifier (a new UUID) in place of its path, in
        its node and in the parts of the root dataset. A node already named by one keeps it. The path
        must stay known: a file whose node has no history is left as it is, and listed. Returns the
        identifiers given, by path, and the paths left.
        """
        graph: List[Any] = document["@graph"]
        given: Dict[str, str] = {}
        left: List[str] = []
        renamed: Dict[str, str] = {}
        for node in graph:
            if not isinstance(node, dict) or not cls._is_file(node) or cls.is_identifier(node.get("@id")):
                continue
            path: Optional[str] = cls.path_of(node)
            has_history: bool = isinstance(node.get(cls.LIST_PROPERTY), list) and len(node[cls.LIST_PROPERTY]) > 0
            if path is None or not has_history:
                if path is not None:
                    left.append(path)
                continue
            identifier: str = str(uuid.uuid4())
            renamed[node["@id"]] = identifier
            given[path] = identifier
            node["@id"] = identifier

        cls._rename_parts(document, renamed)
        return given, sorted(left)

    @classmethod
    def give_identifiers(cls, document: Dict[str, Any], identifiers: Dict[str, str]) -> None:
        """Names the files of the document, by path, with the identifiers they had."""
        renamed: Dict[str, str] = {}
        for node in document["@graph"]:
            if not isinstance(node, dict) or not cls._is_file(node) or cls.is_identifier(node.get("@id")):
                continue
            path: Optional[str] = cls.path_of(node)
            if path is not None and path in identifiers:
                renamed[node["@id"]] = identifiers[path]
                node["@id"] = identifiers[path]
        cls._rename_parts(document, renamed)

    @classmethod
    def _rename_parts(cls, document: Dict[str, Any], renamed: Dict[str, str]) -> None:
        root: Optional[Dict[str, Any]] = next(
            (node for node in document["@graph"] if isinstance(node, dict) and node.get("@id") == cls.ROOT_NODE_ID),
            None,
        )
        if root is None or not isinstance(root.get("hasPart"), list):
            return
        for part in root["hasPart"]:
            if isinstance(part, dict) and part.get("@id") in renamed:
                part["@id"] = renamed[part["@id"]]

    @classmethod
    def read_dataset_entries(cls, crate_data: Any) -> List[DatasetHistoryEntry]:
        """The history of the whole container the root dataset of the crate keeps, in the order it states it."""
        graph: Any = crate_data.get("@graph") if isinstance(crate_data, dict) else None
        root: Any = next(
            (node for node in graph if isinstance(node, dict) and node.get("@id") == cls.ROOT_NODE_ID),
            None,
        ) if isinstance(graph, list) else None
        items: Any = root.get(cls.LIST_PROPERTY) if isinstance(root, dict) else None
        entries: List[DatasetHistoryEntry] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            values: List[Any] = [item.get(cls.FILE_ID_PROPERTY), item.get(cls.PATH_PROPERTY), item.get(cls.HASH_PROPERTY), item.get(cls.TIME_PROPERTY)]
            if all(isinstance(value, str) and value for value in values):
                missing: Any = item.get(cls.MISSING_PROPERTY)
                entries.append(DatasetHistoryEntry(*values, size=cls._size_of(item), missing_since=missing if isinstance(missing, str) and missing else None))
        return entries

    @classmethod
    def set_dataset_entries(cls, document: Dict[str, Any], entries: List[DatasetHistoryEntry]) -> None:
        """Puts the history of the whole container in the root dataset, ordered by timestamp, once each entry."""
        root: Optional[Dict[str, Any]] = next(
            (node for node in document["@graph"] if isinstance(node, dict) and node.get("@id") == cls.ROOT_NODE_ID),
            None,
        )
        if root is None:
            raise ValueError("The RO-Crate has no root dataset.")
        root[cls.LIST_PROPERTY] = [
            cls._item_of(entry)
            for entry in sorted(without_superseded(entries), key=DatasetHistoryEntry.sort_key)
        ]

    @classmethod
    def dataset_entries_of(cls, document: Dict[str, Any]) -> List[DatasetHistoryEntry]:
        """
        What the history of the whole container is with the entries of the files in the document: the
        entries the root dataset already has (the ones of files that are gone stay) and, for each file
        named by an identifier, the entries of its history, each with the identifier of the file.
        """
        entries: List[DatasetHistoryEntry] = cls.read_dataset_entries(document)
        for node in document["@graph"]:
            if not isinstance(node, dict) or not cls._is_file(node) or not cls.is_identifier(node.get("@id")):
                continue
            for entry in cls._history_of_items(node.get(cls.LIST_PROPERTY)):
                entries.append(DatasetHistoryEntry(node["@id"], entry.relative_path, entry.sha256, entry.timestamp, entry.size, entry.missing_since))
        return entries

    @classmethod
    def read_document(cls, crate_file: Path) -> Dict[str, Any]:
        """The crate document that is there."""
        document: Any = json.loads(crate_file.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("@graph"), list):
            raise ValueError(f"{crate_file} is not an RO-Crate.")
        return document

    @classmethod
    def write_document(cls, crate_file: Path, document: Dict[str, Any]) -> None:
        """Writes the crate document, with the terms of the history declared in its context."""
        cls.declare_terms(document)
        crate_file.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def declare_terms(cls, document: Dict[str, Any]) -> None:
        """Declares the terms of the history in the context of the crate document."""
        context: Any = document.get("@context")
        declared: List[Any] = context if isinstance(context, list) else [context]
        terms: Dict[str, str] = next((item for item in declared if isinstance(item, dict)), {})
        if not any(item is terms for item in declared):
            declared.append(terms)
        terms.update(cls.TERMS)
        document["@context"] = declared

    @classmethod
    def matches(cls, files: ContainerFileRepository, histories: Dict[str, FileHistory], relative_paths: Any) -> bool:
        """
        Whether the history knows every file as it is now: the last entry that names each path says the
        file is there, with the timestamp the file has. The content is not read.
        """
        for relative_path in relative_paths:
            modified: Optional[str] = files.modified(relative_path)
            if modified is None:
                return False
            known: Optional[FileHistoryEntry] = histories.get(relative_path, FileHistory()).last_at(relative_path)
            if (
                known is None
                or known.missing_since is not None
                or known.timestamp != modified
            ):
                return False

        return True

    @classmethod
    def _is_file(cls, node: Dict[str, Any]) -> bool:
        node_type: Any = node.get("@type")
        return node_type == cls.FILE_TYPE or (isinstance(node_type, list) and cls.FILE_TYPE in node_type)
