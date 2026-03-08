
import os
from pathlib import Path
from typing import Any, List, Iterable
from ontobdc.module.resource.adapter.folder import LocalFolderAdapter
from ontobdc.module.resource.domain.port.entity import FilesystemPort, FolderPort
from ontobdc.module.resource.domain.port.repository import DatasetRepositoryPort, FileRepositoryPort


class SimpleFileRepository(FileRepositoryPort):
    def __init__(self, root_path: str):
        self._root_path = Path(root_path)

    @property
    def path(self) -> Path:
        return self._root_path

    def iter_file_paths(self) -> Iterable[Path]:
        if not self._root_path.exists():
            return []
        if self._root_path.is_file():
            yield self._root_path
            return
        for p in self._root_path.rglob("*"):
            if p.is_file():
                yield p

    def get_all(self) -> List[Path]:
        return list(self.iter_file_paths())

    # Stub implementations for abstract methods required by FileRepositoryPort
    @property
    def filesystem(self) -> FilesystemPort:
        raise NotImplementedError

    @property
    def path_folders(self) -> List[FolderPort]:
        # Return a simple object that mocks a folder with a path to satisfy HasReadPermission
        class MockFolder:
            def __init__(self, p): self.path = p
        return [MockFolder(self._root_path)]

    def exists(self, path: str) -> bool:
        return (self._root_path / path).exists()

    def get_by_type(self, type_filter: str) -> List[Any]:
        results = []
        ext_filter = type_filter.lower()
        if ext_filter.startswith("."):
            ext_filter = ext_filter[1:]
            
        for path in self.iter_file_paths():
            suffix = path.suffix.lower()
            if suffix.startswith("."):
                suffix = suffix[1:]
                
            if suffix == ext_filter:
                results.append(path)
                
        return results

    def get_by_media_types(self, media_types: List[str]) -> List[Any]:
        return []

    def get_by_mimetype(self, mimetype: str) -> List[Any]:
        return []

    def get_by_name(self, name: str) -> Any:
        return None

    def get_json(self, path: str) -> Any:
        return None

    def open_file(self, path: str, mode: str = "r") -> Any:
        return open(self._root_path / path, mode)

    def rename(self, src: str, dst: str) -> None:
        pass


class LocalObjectDatasetRepository(DatasetRepositoryPort):
    def __init__(self, folder: FolderPort, ensure_path: bool = False) -> None:
        self._folder: FolderPort = folder
        if ensure_path:
            path = getattr(self._folder, "path", None)
            if isinstance(path, str):
                os.makedirs(path, exist_ok=True)
        self._root = getattr(self._folder, "path", None)

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

    def iter_file_paths(self):
        if self._root:
            for root, _, files in os.walk(self._root):
                for file in files:
                    yield Path(os.path.join(root, file))

    def open_file(self, path: str, mode: str = "r") -> Any:
        # If absolute path and inside root, allow.
        # If relative path, join with root.
        
        target_path = path
        if not os.path.isabs(path) and self._root:
            target_path = os.path.join(self._root, path)
            
        # If writing, ensure directory exists
        if 'w' in mode or 'a' in mode:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            return open(target_path, mode, encoding='utf-8' if 'b' not in mode else None)

        if os.path.exists(target_path):
            return open(target_path, mode, encoding='utf-8' if 'b' not in mode else None)
        return None

    def exists(self, path: str) -> bool:
        if not self._root:
            return False
        
        target_path = path
        if not os.path.isabs(path):
            target_path = os.path.join(self._root, path)
            
        return os.path.exists(target_path)

    def rename(self, src: str, dst: str) -> None:
        if not self._root:
            return

        src_path = src
        if not os.path.isabs(src):
            src_path = os.path.join(self._root, src)
            
        dst_path = dst
        if not os.path.isabs(dst):
            dst_path = os.path.join(self._root, dst)
            
        if os.path.exists(src_path):
            os.rename(src_path, dst_path)

    def get_json(self, path: str) -> Any:
        import json
        if not self._root:
            return None
        full_path = os.path.join(self._root, path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return None
        return None

