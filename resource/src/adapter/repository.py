
import os
from typing import Any, List
from ontobdc.resource.src.domain.port.entity import FilesystemPort, FolderPort
from ontobdc.resource.src.domain.port.repository import DatasetRepositoryPort


class LocalObjectDatasetRepository(DatasetRepositoryPort):
    def __init__(self, folder: FolderPort, ensure_path: bool = False) -> None:
        self._folder: FolderPort = folder
        if ensure_path:
            path = getattr(self._folder, "path", None)
            if isinstance(path, str):
                os.makedirs(path, exist_ok=True)

    @property
    def filesystem(self) -> FilesystemPort:
        return getattr(self._folder, "filesystem", None)

    @property
    def path_folders(self) -> List[FolderPort]:
        return getattr(self._folder, "path_folders", [self._folder])

    def get_by_id(self, id: str) -> List[Any]:
        if hasattr(self._folder, "get_by_id"):
            return self._folder.get_by_id(id)
        return []

    def get_all(self) -> List[Any]:
        if hasattr(self._folder, "get_all"):
            return self._folder.get_all()
        return []

    def get_by_type(self, type: str) -> List[Any]:
        if hasattr(self._folder, "get_by_type"):
            return self._folder.get_by_type(type)
        return []
