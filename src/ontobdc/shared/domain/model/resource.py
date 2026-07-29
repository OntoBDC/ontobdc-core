
import requests
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import ParseResult, urlparse

from ontobdc.shared.adapter.util import to_snake_case
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from ontobdc.shared.domain.port.resource import UrlResourcePort


class UrlResource(BaseModel, UrlResourcePort):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    target_url: str = Field(alias="url", description="The remote resource URL.")
    _name: Optional[str] = PrivateAttr(default=None)
    _dataset: Optional["DatasetRepositoryPort"] = PrivateAttr(default=None)

    def __init__(self, url: str) -> None:
        super().__init__(target_url=url)

    @property
    def url(self) -> str:
        return self.target_url

    @property
    def name(self) -> str:
        if isinstance(self._name, str) and self._name and len(self._name) > 2:
            return self._name

        parsed_url: ParseResult = urlparse(self.target_url)
        return parsed_url.path.split("/")[-1] or "remote_resource"

    @property
    def dataset(self) -> Optional["DatasetRepositoryPort"]:
        return self._dataset

    @property
    def container(self) -> Optional[Any]:
        dataset: Optional["DatasetRepositoryPort"] = self.dataset
        if dataset is not None:
            return dataset.container

        return None

    @property
    def mimetype(self) -> str:
        return "application/octet-stream"

    def to_json(self) -> Dict[str, Any]:
        return {"url": self.target_url, "type": "url"}

    def write(self, dataset: "DatasetRepositoryPort") -> None:
        self._dataset = dataset

    def exists(self) -> bool:
        try:
            response: requests.Response = requests.head(self.target_url, timeout=5)
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


class UrlContentResource(BaseModel, UrlResourcePort):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = Field(description="Inline HTML content fetched from a URL.")
    _name: Optional[str] = PrivateAttr(default=None)
    _dataset: Optional["DatasetRepositoryPort"] = PrivateAttr(default=None)

    def __init__(self, content: str) -> None:
        super().__init__(content=content)

    @property
    def url(self) -> str:
        return ""

    @property
    def dataset(self) -> Optional["DatasetRepositoryPort"]:
        return self._dataset

    @property
    def container(self) -> Optional[Any]:
        dataset: Optional["DatasetRepositoryPort"] = self.dataset
        if dataset is not None:
            return dataset.container

        return None

    @property
    def name(self) -> str:
        if isinstance(self._name, str) and self._name and len(self._name) > 2:
            return self._name

        title: str = "url_content"
        if "<title>" in self.content and "</title>" in self.content:
            title_start: int = self.content.find("<title>") + 7
            title_end: int = self.content.find("</title>")
            extracted_title: str = self.content[title_start:title_end].strip()
            if extracted_title:
                title = extracted_title

        return to_snake_case(title)

    @property
    def path(self) -> Path:
        dataset: Optional["DatasetRepositoryPort"] = self.dataset
        if dataset is not None:
            return dataset.path / f"{self.name}.html"

        raise FileNotFoundError("Url content resource must be written to dataset first.")

    @property
    def mimetype(self) -> str:
        return "text/html"

    def to_json(self) -> Dict[str, Any]:
        return {"content": self.content, "type": "url_content"}

    def write(self, dataset: "DatasetRepositoryPort") -> None:
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
