from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ontobdc.storage.adapter.container_file_repository import ContainerFileRepository
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import FileHistory, FileHistoryEntry


class FileLedger:
    """
    What a container has ever known of its files, to say which file a file on disk is. The history of
    every file is in the crate: in its node while the file is there, and in the root dataset, with the
    identifier of the file, whatever became of the node. A file on disk is identified by that
    history, wherever it is and whether or not the crate states it: it is the file that once held
    its content (or, when the content is not known, had its name and size).

    The ledger reads the crate document it is given and changes it. The caller writes it.
    """

    def __init__(self, document: Dict[str, Any], files: ContainerFileRepository) -> None:
        self.document: Dict[str, Any] = document
        self.files: ContainerFileRepository = files
        self.nodes: Dict[str, Dict[str, Any]] = {
            node["@id"]: node
            for node in document["@graph"]
            if isinstance(node, dict) and CrateFileHistory._is_file(node) and isinstance(node.get("@id"), str)
        }
        self.owners: Dict[str, str] = CrateFileHistory.owners(document)
        self.histories: Dict[str, FileHistory] = {}
        kept: Dict[str, List[FileHistoryEntry]] = {}
        for entry in CrateFileHistory.read_dataset_entries(document):
            kept.setdefault(entry.file_id, []).append(
                FileHistoryEntry(entry.relative_path, entry.sha256, entry.timestamp, entry.size, entry.missing_since)
            )
        for node_id, history in CrateFileHistory.node_histories(document).items():
            self.histories[node_id] = history.with_entries(kept.pop(node_id, []))
        for gone_id, entries in kept.items():
            self.histories[gone_id] = FileHistory(entries)

    # -- what is known -------------------------------------------------------------------------

    def is_alive(self, file_id: str) -> bool:
        """Whether the file is on disk at any path its history says it is at."""
        return any(self.files.is_file(path) for path in self.histories[file_id].live_paths())

    def has_node(self, file_id: str) -> bool:
        return file_id in self.nodes

    def sizes(self) -> Set[Optional[int]]:
        """The sizes the history has seen; None is in it when an entry does not know its size."""
        return {entry.size for history in self.histories.values() for entry in history}

    def targets(self) -> List[str]:
        """
        The files on disk to identify: the ones no node is at, and the ones a node named by its path
        is at (a node a refresh made for a file it did not know). A node named by an identifier has
        been identified already.
        """
        return [
            path for path in self.files.list()
            if self.owners.get(path) is None or not CrateFileHistory.is_identifier(self.owners[path])
        ]

    def by_content(self, path: str, sha256: str, owner: Optional[str]) -> List[str]:
        """The identifiers of the files that once held this content, the owner of the path left out."""
        return [
            file_id for file_id, history in self.histories.items()
            if file_id != owner and any(entry.sha256 == sha256 for entry in history)
        ]

    def by_name_and_size(self, name: str, size: int, owner: Optional[str]) -> List[str]:
        """The identifiers of the files that once had this name and size, the owner of the path left out."""
        return [
            file_id for file_id, history in self.histories.items()
            if file_id != owner and any(Path(entry.relative_path).name == name and entry.size == size for entry in history)
        ]

    def named(self, file_ids: List[str], name: str) -> List[str]:
        """Of these files, the ones that were once named so."""
        return [
            file_id for file_id in file_ids
            if any(Path(entry.relative_path).name == name for entry in self.histories[file_id])
        ]

    def can_take(self, file_id: str, owner: Optional[str]) -> bool:
        """
        Whether a file on disk, with this owner, may be taken for the file. Nothing owns it: yes. A node
        named by its path owns it (the refresh made it): yes when the file is named by an identifier,
        or has no node (so is not another file that is there); when the file is a node named by its path
        too, they were both there, and are two files.
        """
        if owner is None:
            return True
        return not self.has_node(file_id) or CrateFileHistory.is_identifier(file_id)

    # -- what is changed -----------------------------------------------------------------------

    def take(self, path: str, file_id: str, entry: FileHistoryEntry, owner: Optional[str]) -> Dict[str, str]:
        """
        Makes the file on disk at ``path`` the file ``file_id``, with ``entry`` as where it is now:
        its history gets the entry. When the file has no node, a node (or the node the refresh made for
        the path) is named by it. Returns what was done.
        """
        before: Optional[FileHistoryEntry] = self.histories[file_id].current()
        origin: str = before.relative_path if before is not None else ""
        if owner is not None and owner != file_id:
            owned: FileHistory = self.histories[owner]
            if self.has_node(file_id):
                self._drop_node(owner)
            else:
                self._rename_node(owner, file_id)
                self.histories[file_id] = self.histories[file_id].with_entries(owned)
            self.histories.pop(owner, None)
        elif owner is None and not self.has_node(file_id):
            self._create_node(file_id, path)

        history: FileHistory = self.histories[file_id].with_entries([entry])
        self.histories[file_id] = history
        CrateFileHistory.set_node_history(self.document, file_id, history)
        file_id = self._follow_path(file_id)
        self.owners = CrateFileHistory.owners(self.document)
        # A node named by its path has no identifier to tell yet: the next states give it one.
        return {"from": origin, "to": path, **({"id": file_id} if CrateFileHistory.is_identifier(file_id) else {})}

    def _drop_node(self, node_id: str) -> None:
        self.document["@graph"] = [node for node in self.document["@graph"] if not (isinstance(node, dict) and node.get("@id") == node_id)]
        self._replace_part(node_id, None)
        self.nodes.pop(node_id, None)

    def _rename_node(self, old_id: str, new_id: str) -> None:
        node: Dict[str, Any] = self.nodes.pop(old_id)
        node["@id"] = new_id
        self.nodes[new_id] = node
        self._replace_part(old_id, new_id)

    def _create_node(self, file_id: str, path: str) -> None:
        properties: Optional[Dict[str, Any]] = self.files.properties(path)
        node: Dict[str, Any] = {"@id": file_id, "@type": "File", **(properties or {})}
        self.document["@graph"].append(node)
        self.nodes[file_id] = node
        self._replace_part(None, file_id)

    def _replace_part(self, old_id: Optional[str], new_id: Optional[str]) -> None:
        root: Optional[Dict[str, Any]] = next(
            (node for node in self.document["@graph"] if isinstance(node, dict) and node.get("@id") == CrateFileHistory.ROOT_NODE_ID),
            None,
        )
        if root is None:
            return
        parts: List[Any] = [part for part in root.get("hasPart", []) if not (isinstance(part, dict) and part.get("@id") == old_id)]
        if new_id is not None and not any(isinstance(part, dict) and part.get("@id") == new_id for part in parts):
            parts.append({"@id": new_id})
        root["hasPart"] = parts

    def _follow_path(self, file_id: str) -> str:
        """A node named by its path is named by the path the file is at: when it is not on disk at the old one, by the current. Returns the id."""
        if CrateFileHistory.is_identifier(file_id):
            return file_id
        current: Optional[FileHistoryEntry] = self.histories[file_id].current()
        old_path: Optional[str] = CrateFileHistory.path_of(self.nodes[file_id])
        if current is None or old_path is None or current.relative_path == old_path or self.files.is_file(old_path):
            return file_id
        new_id: str = current.relative_path
        self._rename_node(file_id, new_id)
        self.histories[new_id] = self.histories.pop(file_id)
        return new_id

    def orphan_paths(self) -> Dict[str, Set[str]]:
        """Of each file with a node, the paths its history says it is at and are not on disk."""
        return {
            file_id: {path for path in self.histories[file_id].live_paths() if not self.files.is_file(path)}
            for file_id in self.nodes
        }

    def publish_lists(self, context: Any) -> None:
        """Tells the next states which of the paths the crate states are on disk and which are not."""
        from ontobdc.storage.plugin.machine.file_reconciliation.port import FileReconciliationRequestPort as Request

        stated: List[str] = sorted(CrateFileHistory.owners(self.document))
        context.set_parameter_value(Request.EXISTING_KEY, [path for path in stated if self.files.is_file(path)])
        context.set_parameter_value(Request.MISSING_KEY, [path for path in stated if not self.files.is_file(path)])
