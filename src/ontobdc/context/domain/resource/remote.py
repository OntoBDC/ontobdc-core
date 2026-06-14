
import json
from rdflib import URIRef
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class RemoteCapabilityMetadata:
    identifier: str
    title: Dict[str, str]
    description: Dict[str, str]
    document_ref: Optional[URIRef] = None

    def get_description(self, lang: str = "en") -> str:
        return self.description.get(lang, "")

    def get_title(self, lang: str = "en") -> str:
        return self.title.get(lang, "")

    def __str__(self):
        data = {
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "document_ref": str(self.document_ref) if self.document_ref else None
        }
        return json.dumps(data, indent=4, ensure_ascii=False)

    __repr__ = __str__


@dataclass
class EntityMetadata:
    class_uri: URIRef
    title: Dict[str, str]
    description: Dict[str, str]
    document_ref: Optional[URIRef] = None

    def get_title(self, lang: str = "en") -> str:
        return self.title.get(lang, "")

    def get_description(self, lang: str = "en") -> str:
        return self.description.get(lang, "")

    def __str__(self):
        data = {
            "class_uri": str(self.class_uri),
            "title": self.title,
            "description": self.description,
            "document_ref": str(self.document_ref) if self.document_ref else None
        }
        return json.dumps(data, indent=4, ensure_ascii=False)

    __repr__ = __str__

