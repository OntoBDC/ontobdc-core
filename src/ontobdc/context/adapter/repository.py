import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Type

from ontobdc.shared.domain.port.resource import FileResourcePort


class LocalContextFileResource(FileResourcePort):
    def __init__(self, file_path: Path):
        self._path: Path = Path(file_path).expanduser().resolve()

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def container(self) -> None:
        return None

    @property
    def dataset(self) -> None:
        return None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def mimetype(self) -> str:
        detected_mimetype, _ = mimetypes.guess_type(str(self._path))
        return detected_mimetype or "application/octet-stream"

    @property
    def content(self) -> Any:
        if not self._path.exists():
            raise FileNotFoundError(str(self._path))

        if self.is_text():
            return self._path.read_text(encoding="utf-8")

        return self._path.read_bytes()

    def exists(self) -> bool:
        return self._path.exists()

    def is_text(self) -> bool:
        return (
            self._path.suffix.lower() in {".txt", ".md", ".json", ".ttl", ".yaml", ".yml"}
            or self.mimetype.startswith("text/")
            or self.mimetype in {"application/json", "application/ld+json"}
        )

    def is_binary(self) -> bool:
        return not self.is_text()

    def is_multimedia(self) -> bool:
        return self.mimetype.startswith(("image/", "audio/", "video/"))

    def is_dict(self) -> bool:
        return self._path.suffix.lower() == ".json"

    def rename(self, dst: Path) -> None:
        self._path = self._path.rename(dst)

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self._path),
            "uri": self._path.as_uri(),
            "mimetype": self.mimetype,
        }

    def write(self, dataset: Any) -> None:
        raise NotImplementedError("LocalContextFileResource.write is not supported.")


class EntityLearningStepRepository:
    FILE_TYPES: List[str] = ["yaml", "yml", "jsonld", "json", "ttl", "md", "txt", "rdf", "xml"]

    def __init__(self, root_path: str, source_path: str) -> None:
        self._root_path: Path = Path(root_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Learning source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "learning" / "entity" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def source_hash(self) -> str:
        return self._source_hash

    @property
    def step_dir(self) -> Path:
        return self._step_dir

    def reload(self, state: Any) -> LocalContextFileResource:
        state_value: str = str(state.value)
        if state_value == "__undefined__":
            return LocalContextFileResource(self._source_path)

        for file_type in self.FILE_TYPES:
            candidate_path: Path = self._step_dir / f"{state_value}.{file_type}"
            if candidate_path.exists():
                return LocalContextFileResource(candidate_path)

        raise FileNotFoundError(f"Learning step not found for '{state_value}' in '{self._step_dir}'.")

    def save(self, state: Any, resource: LocalContextFileResource) -> None:
        extension: str = resource.path.suffix.lstrip(".").strip().lower()
        if extension not in self.FILE_TYPES:
            extension = "json"
            target_path: Path = self._step_dir / f"{state.value}.{extension}"
            target_path.write_text(
                json.dumps(resource.to_json(), ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return

        target_path = self._step_dir / f"{state.value}.{extension}"
        if resource.path != target_path:
            if resource.is_text():
                target_path.write_text(str(resource.content), encoding="utf-8")
            else:
                target_path.write_bytes(resource.content)

    def exists(self, state: Any) -> bool:
        if str(state.value) == "__undefined__":
            return True

        for file_type in self.FILE_TYPES:
            if (self._step_dir / f"{state.value}.{file_type}").exists():
                return True
        return False

    def delete(self, state: Any) -> None:
        for candidate_path in self._step_dir.glob(f"{state.value}.*"):
            if candidate_path.is_file():
                candidate_path.unlink()

    def all(self, state_class: Type[Any]) -> List[Any]:
        states: List[Any] = []
        for candidate_path in self._step_dir.iterdir():
            if not candidate_path.is_file():
                continue
            if candidate_path.suffix.lstrip(".").lower() not in self.FILE_TYPES:
                continue
            try:
                states.append(state_class(candidate_path.stem))
            except Exception:
                continue
        return states

    def write_text_file(
        self,
        state: Any,
        content: str,
        file_type: str = "txt",
        encoding: str = "utf-8",
    ) -> Path:
        target_path: Path = self._step_dir / f"{state.value}.{file_type}"
        target_path.write_text(content, encoding=encoding)
        return target_path


class EntityAnalysisStepRepository(EntityLearningStepRepository):
    def __init__(self, root_path: str, source_path: str) -> None:
        self._root_path: Path = Path(root_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Analysis source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "analysis" / "entity" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)


class DocumentImportStepRepository(EntityLearningStepRepository):
    def __init__(self, container_path: str, source_path: str) -> None:
        self._root_path: Path = Path(container_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Import source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "import" / "document" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)
