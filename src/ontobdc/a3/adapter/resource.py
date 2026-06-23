
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
from ontobdc.storage.domain.port.resource import TextFileResourcePort
from ontobdc.storage.domain.port.dataset import DatasetRepositoryPort


class RawTextResourceAdapter(TextFileResourcePort):
    """
    Adapter to represent raw free text as a text file resource.
    """

    def __init__(self, raw_text: str):
        self._raw_text: str = raw_text
        self._dataset: Optional[DatasetRepositoryPort] = None
        self._hash: Optional[str] = None

    @property
    def hash(self) -> str:
        if not isinstance(self._hash, str):
            normalized_text: str = self.content.replace("\n", " ")
            normalized_text = re.sub(r"\s+", " ", normalized_text)
            normalized_text = normalized_text.strip().lower()
            self._hash = hashlib.md5(normalized_text.encode("utf-8")).hexdigest()

        return self._hash

    @property
    def name(self) -> str:
        return "raw"

    @property
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        return self._dataset

    @property
    def container(self):
        if self._dataset is None:
            return None

        return self._dataset.container

    @property
    def path(self) -> Path:
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.path / self.hash / (self.name + ".txt")

        raise FileNotFoundError("Raw text resource must be written to a dataset first.")

    @property
    def mimetype(self) -> str:
        return "text/plain"

    @property
    def content(self) -> str:
        return self._raw_text

    def exists(self) -> bool:
        return True

    def rename(self, dst: Path) -> None:
        raise NotImplementedError("Renaming is not supported for raw text resources.")

    def delete(self) -> None:
        raise NotImplementedError("Deleting is not supported for raw text resources.")

    def write(self, dataset: DatasetRepositoryPort) -> None:
        self._dataset = dataset
        target_path: Path = self.path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.content, encoding="utf-8")

    def is_binary(self) -> bool:
        return False

    def is_multimedia(self) -> bool:
        return False

    def is_dict(self) -> bool:
        return False

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "mimetype": self.mimetype,
            "content": self._raw_text,
        }
