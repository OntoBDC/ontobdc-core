import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.storage.adapter.bootstrap import StoragePathStatHelper, StorageLayoutConstants
from ontobdc.storage.adapter.crate_file_properties import CrateFileProperties
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.domain.model.file_history import FileHistoryEntry


class ContainerFileRepository:
    """
    The files a container holds on disk, by their path in it (``docs/a.txt``, always with slashes).
    It is where the container's files are listed, looked at (stat, hash, the properties the crate
    states) and read: the crate, the history, the check and the reconciliation ask it, and none of
    them walks the directory or opens a file of the container itself. What the crate says about the
    files is ``ContainerRoCrate``'s; what the disk holds is this.
    """

    CHUNK_BYTES: int = 1024 * 1024
    GENERATED_SURFACE_FILE_NAME: str = "index.html"
    DATASET_LINKSET_DIR_NAME: str = "linkset"
    DATASET_DATAPACKAGE_FILE_NAME: str = "datapackage.json"
    DATASET_MARKER_FILE_NAMES = (StorageLayoutConstants.DATASET_STORAGE_FILE_NAME, "nid.ttl")

    def __init__(self, container_path: Path) -> None:
        self._root: Path = Path(container_path)

    @property
    def root(self) -> Path:
        return self._root

    def location(self, relative_path: str) -> Path:
        """Where the file is on disk."""
        return self._root / Path(relative_path)

    def is_file(self, relative_path: str) -> bool:
        return self.location(relative_path).is_file()

    def stat(self, relative_path: str) -> Any:
        """The stat of the file; None when it cannot be seen, which is only acceptable for one that vanished."""
        return StoragePathStatHelper.safe_stat(self.location(relative_path))

    def size(self, relative_path: str) -> Optional[int]:
        stat_result: Any = self.stat(relative_path)
        return None if stat_result is None else int(stat_result.st_size)

    def modified(self, relative_path: str) -> Optional[str]:
        """When the file was last modified, in UTC (when created, if the system tells no modification time)."""
        stat_result: Any = self.stat(relative_path)
        return None if stat_result is None else CrateFileProperties.modification_time(stat_result)

    def properties(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """The properties the crate states for the file; None when it cannot be seen."""
        return CrateFileProperties.of(self.location(relative_path))

    def sha256(self, relative_path: str) -> str:
        """The SHA-256 of the content, as lowercase hexadecimal."""
        digest: Any = hashlib.sha256()
        with self.location(relative_path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(self.CHUNK_BYTES), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        return self.location(relative_path).read_text(encoding=encoding)

    def entry(self, relative_path: str, sha256: Optional[str] = None) -> Optional[FileHistoryEntry]:
        """
        What the file is now, as an entry of its history: its path, the hash of its content (read, unless
        it is given), its timestamp and its size. None when it cannot be seen.
        """
        stat_result: Any = self.stat(relative_path)
        timestamp: Optional[str] = CrateFileProperties.modification_time(stat_result) if stat_result is not None else None
        if stat_result is None or timestamp is None:
            return None
        return FileHistoryEntry(relative_path, sha256 or self.sha256(relative_path), timestamp, int(stat_result.st_size))

    def list(self) -> List[str]:
        """
        The files the container publishes, by path, sorted: not the ones in a directory that starts with a
        dot (the container's own metadata) or is a dataset of its own, not the ones that are blocked from
        publication, not the surface the container generates.
        """
        files: List[str] = []
        for directory, subdirectories, names in os.walk(self._root, topdown=True):
            directory_path: Path = Path(directory)
            subdirectories[:] = [
                name for name in subdirectories
                if not name.startswith(".")
                and name != StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
                and not self._is_dataset(directory_path / name)
            ]
            for name in names:
                if ContainerDataPackageSynchronizer.is_file_blocked_from_publication(name):
                    continue
                relative: str = (directory_path / name).relative_to(self._root).as_posix()
                if relative.strip() and relative != self.GENERATED_SURFACE_FILE_NAME:
                    files.append(relative)
        return sorted(set(files))

    def _is_dataset(self, directory: Path) -> bool:
        marker_directory: Path = directory / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
        if marker_directory.is_dir() and any((marker_directory / name).is_file() for name in self.DATASET_MARKER_FILE_NAMES):
            return True
        return (directory / self.DATASET_LINKSET_DIR_NAME / self.DATASET_DATAPACKAGE_FILE_NAME).is_file()
