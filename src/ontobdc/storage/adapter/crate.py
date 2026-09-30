import json
import hashlib
from pathlib import Path
from typing import Any, ClassVar, Dict, List
from urllib.parse import unquote

from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerRoCrate:
    """
    Reads the RO-Crate of a container: what the container says it holds.

    The crate is the container's own statement about its files, which is
    not the same thing as what a walk of the directory finds. The two
    differ exactly when the container is out of step with its crate, and
    that is the moment the difference matters — a caller asking the crate
    is asking what the container declares, and must not be handed the
    disk instead.

    A crate states a path as a URI reference, so what it carries is
    percent-encoded and may be written against the crate's own root. What
    comes back is the path as a person would name it, relative to the
    container.
    """

    ROOT_NODE_ID: ClassVar[str] = "./"
    GRAPH_KEY: ClassVar[str] = "@graph"
    NODE_ID_KEY: ClassVar[str] = "@id"
    HAS_PART_KEY: ClassVar[str] = "hasPart"

    @classmethod
    def file_paths(cls, container_path: Path) -> List[str]:
        """
        Return the path of every file the container's crate states.
        """
        root_node: Dict[str, Any] = cls._root_node_of(cls.of(container_path))
        parts: Any = root_node.get(cls.HAS_PART_KEY)
        if parts is None:
            return []

        if not isinstance(parts, list):
            raise ValueError(
                f"The RO-Crate of the container at {container_path} states "
                f"its parts as something other than a list."
            )

        file_paths: List[str] = []
        part: Any
        for part in parts:
            if not isinstance(part, dict):
                continue

            part_id: Any = part.get(cls.NODE_ID_KEY)
            if not isinstance(part_id, str) or not part_id.strip():
                continue

            file_paths.append(cls._path_of(part_id))

        return sorted(file_paths)

    @classmethod
    def file_hash(cls, container_path: Path) -> str:
        """
        Return a fingerprint of the file paths the crate currently states.

        Hashes the path list the crate declares, not the crate document
        itself, so a caller can tell whether the set of files a crate
        states has changed since a fingerprint was last recorded, without
        being tripped up by unrelated crate properties (timestamps, sizes)
        that leave the file set itself untouched.
        """
        digest_source: str = "\n".join(cls.file_paths(container_path))
        return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()

    @classmethod
    def of(cls, container_path: Path) -> Dict[str, Any]:
        """
        Return the RO-Crate of the container at the given path.
        """
        crate_path: Path = StorageBootstrap.get_container_crate_metadata_file_path(
            container_path,
        )
        if not crate_path.is_file():
            raise ValueError(
                f"The container at {container_path} carries no RO-Crate."
            )

        crate: Any = json.loads(crate_path.read_text(encoding="utf-8"))
        if not isinstance(crate, dict):
            raise ValueError(f"The RO-Crate at {crate_path} is not a JSON object.")

        return crate

    @classmethod
    def _root_node_of(cls, crate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return the node the crate describes the container itself with.
        """
        graph: Any = crate.get(cls.GRAPH_KEY)
        if not isinstance(graph, list):
            raise ValueError("The RO-Crate states no graph.")

        node: Any
        for node in graph:
            if isinstance(node, dict) and node.get(cls.NODE_ID_KEY) == cls.ROOT_NODE_ID:
                return node

        raise ValueError(
            f"The RO-Crate describes no {cls.ROOT_NODE_ID} node, so it says "
            f"nothing about what the container holds."
        )

    @classmethod
    def _path_of(cls, node_id: str) -> str:
        """
        Return the path a crate id names, as the name it was given.
        """
        file_path: str = unquote(node_id.strip())
        if file_path.startswith(cls.ROOT_NODE_ID):
            return file_path[len(cls.ROOT_NODE_ID):]

        return file_path
