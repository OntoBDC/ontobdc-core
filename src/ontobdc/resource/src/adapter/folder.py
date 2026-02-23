from pathlib import Path
from typing import Any, List

from ontobdc.core.src.domain.schema.entity import SchemaEntity
from ontobdc.resource.src.domain.exception import OntoBDCPathNotFound


class LocalFolderAdapter:
    def __init__(self, entity: SchemaEntity, **runtime: Any) -> None:
        self._entity = entity
        self._filesystem = runtime.get("filesystem")
        self.path = runtime.get("path")
        self.segment_separator = runtime.get("segment_separator")
        for k, v in runtime.items():
            if k not in {"filesystem", "path", "segment_separator"}:
                setattr(self, k, v)

    @property
    def filesystem(self) -> Any:
        return self._filesystem

    @property
    def path_folders(self) -> List[Any]:
        return [self]

    def get_all(self) -> List[Any]:
        base = Path(getattr(self, "path"))
        if not base.exists():
            raise OntoBDCPathNotFound(str(base))
        out: List[str] = []
        for p in base.rglob("*"):
            if p.is_file():
                out.append(str(p))
        return out

    def get_by_id(self, id: str) -> List[Any]:
        base = Path(getattr(self, "path"))
        if not base.exists():
            raise OntoBDCPathNotFound(str(base))
        matches: List[str] = []
        for p in base.rglob("*"):
            if p.is_file() and p.name == id:
                matches.append(str(p))
        return matches

    def get_by_type(self, type: str) -> List[Any]:
        base = Path(getattr(self, "path"))
        if not base.exists():
            raise OntoBDCPathNotFound(str(base))

        matches: List[str] = []
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lstrip(".") == type:
                matches.append(str(p))

        return matches
