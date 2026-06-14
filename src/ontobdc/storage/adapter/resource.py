
import time
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional
from ontobdc.shared.adapter.util import to_snake_case
from ontobdc.storage.domain.port.dataset import DatasetRepositoryPort
from ontobdc.storage.domain.port.resource import UrlResourcePort, TextFileResourcePort, FileResourcePort


class TextFileResource(TextFileResourcePort):
    def __init__(self, content: str):
        self._content: str = content
        self._name: Optional[str] = None
        self._dataset: Optional[DatasetRepositoryPort] = None

    @property
    def content(self) -> str:
        return self._content

    @property
    def name(self) -> str:
        if isinstance(self._name, str) and self._name and len(self._name) > 2:
            return self._name

        return 'text_file_' + time.strftime("%Y%m%d%H%M%S", time.localtime())

    @property
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        return self._dataset

    @property
    def container(self):
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.container

        return None

    @property
    def path(self) -> Path:
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.path / (self.name + ".txt")

        raise FileNotFoundError("Text file resource must be written to dataset first.")

    @property
    def mimetype(self) -> str:
        return "text/html"

    def to_json(self) -> Dict[str, Any]:
        return {"content": self._content, "type": "html"}
        
    def write(self, dataset: DatasetRepositoryPort) -> None:
        self._dataset = dataset

    def exists(self) -> bool:
        return True

    def rename(self, dst: Path) -> None:
        pass

    def delete(self) -> None:
        pass

    def is_binary(self) -> bool:
        return False

    def is_multimedia(self) -> bool:
        return False

    def is_dict(self) -> bool:
        return False
        
    def is_text(self) -> bool:
        return True


class UrlResource(UrlResourcePort):
    def __init__(self, url: str):
        self._url: str = url
        self._name: Optional[str] = None
        self._dataset: Optional[DatasetRepositoryPort] = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def name(self) -> str:
        if isinstance(self._name, str) and self._name and len(self._name) > 2:
            return self._name

        from urllib.parse import urlparse
        parsed_url = urlparse(self._url)
        return parsed_url.path.split("/")[-1] or "remote_resource"

    @property
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        return self._dataset

    @property
    def container(self):
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.container

        return None

    @property
    def mimetype(self) -> str:
        return "application/octet-stream"

    def to_json(self) -> Dict[str, Any]:
        return {"url": self._url, "type": "url"}

    def write(self, dataset: DatasetRepositoryPort) -> None:
        self._dataset = dataset

    def exists(self) -> bool:
        try:
            import requests
            response = requests.head(self._url, timeout=5)
            return response.status_code < 400
        except Exception:
            return False

    def is_text(self) -> bool:
        return False

    def is_binary(self) -> bool:
        return True

    def is_multimedia(self) -> bool:
        return False

    def is_dict(self) -> bool:
        return False

    def download(self) -> None:
        raise NotImplementedError("Download not implemented yet.")


class UrlContentResource(UrlResourcePort):
    def __init__(self, content: str):
        self._content = content
        self._name: Optional[str] = None
        self._dataset: Optional[DatasetRepositoryPort] = None

    @property
    def url(self) -> str:
        return ""

    @property
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        return self._dataset

    @property
    def container(self):
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.container

        return None

    @property
    def name(self) -> str:
        if isinstance(self._name, str) and self._name and len(self._name) > 2:
            return self._name
            
        # Extract title from HTML content if present
        title = "url_content"
        if "<title>" in self._content and "</title>" in self._content:
            title_start = self._content.find("<title>") + 7
            title_end = self._content.find("</title>")
            extracted_title = self._content[title_start:title_end].strip()
            if extracted_title:
                title = extracted_title
        
        return f"{to_snake_case(title)}"
        
    @property
    def path(self) -> Path:
        if isinstance(self._dataset, DatasetRepositoryPort):
            return self._dataset.path / (self.name + ".html")

        raise FileNotFoundError("Url content resource must be written to dataset first.")
        
    @property
    def mimetype(self) -> str:
        return "text/html"

    def to_json(self) -> Dict[str, Any]:
        return {"content": self._content, "type": "url_content"}

    def write(self, dataset: DatasetRepositoryPort) -> None:
        self._dataset = dataset

    def exists(self) -> bool:
        return True

    def is_text(self) -> bool:
        return True

    def is_binary(self) -> bool:
        return False

    def is_multimedia(self) -> bool:
        return False

    def is_dict(self) -> bool:
        return False

    def download(self) -> None:
        raise NotImplementedError("UrlContentResource is already downloaded.")


class LocalFileResource(FileResourcePort):
    def __init__(self, file_path: Path):
        self._path = Path(file_path)
        self._dataset: Optional[DatasetRepositoryPort] = None

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def dataset(self) -> Optional[DatasetRepositoryPort]:
        if not isinstance(self._dataset, DatasetRepositoryPort):
            from ontobdc.storage import get_storage_file
            from ontobdc.storage.adapter.repository import LoadedStorageGraph

            storage_graph = LoadedStorageGraph(get_storage_file())
            for candidate_dir in (self._path.parent, *self._path.parent.parents):
                dataset = storage_graph.get_dataset(dataset_location=str(candidate_dir))
                if dataset is not None:
                    self._dataset = dataset
                    break

        return self._dataset

    @property
    def container(self):
        dataset = self.dataset
        if isinstance(dataset, DatasetRepositoryPort):
            return dataset.container

        return None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def mimetype(self) -> str:
        return mimetypes.guess_type(str(self._path))[0] or "application/octet-stream"

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "mimetype": self.mimetype,
        }

    def write(self, dataset: DatasetRepositoryPort) -> None:
        raise NotImplementedError("Local file resources are read-only.")

    def exists(self) -> bool:
        return self._path.exists()

    def rename(self, dst: Path) -> None:
        self._path = self._path.rename(dst)

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)

    def is_text(self) -> bool:
        return self.mimetype.startswith("text/")

    def is_binary(self) -> bool:
        return not self.is_text() and not self.is_multimedia()

    def is_multimedia(self) -> bool:
        return self.mimetype.startswith("image/") or self.mimetype.startswith("audio/") or self.mimetype.startswith("video/")

    def is_dict(self) -> bool:
        return self.mimetype in {"application/json", "application/ld+json"}


class TripleFileResource(LocalFileResource):
    """
    A resource representing an RDF triple file.
    """
    def is_text(self) -> bool:
        return False

    def is_binary(self) -> bool:
        return False

    def is_multimedia(self) -> bool:
        return False

    def is_dict(self) -> bool:
        return False

    def is_triple(self) -> bool:
        return True
