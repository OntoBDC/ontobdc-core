
from rdflib import DCTERMS
from sre_compile import isstring
from typing import Any, Dict, List, Optional


class Entity:
    def __init__(self, manifest: Dict[str, Any]):
        self._manifest = manifest

    @property
    def id(self) -> str:
        return self._manifest['@id']
    
    @property
    def title(self) -> str:
        dcterms: str = self._get_ontology_prefix(str(DCTERMS))
        return self._manifest[f"{dcterms}:title"]

    @property
    def description(self) -> str:
        dcterms: str = self._get_ontology_prefix(str(DCTERMS))
        return self._manifest[f"{dcterms}:description"]

    @property
    def package(self) -> List[str]:
        """
        Get the package of the entity.
        """
        ct: Optional[str] = self._get_ontology_prefix("https://standards.iso.org/iso/21597/-1/ed-1/en/Container#")
        if ct is None:
            raise ValueError("Container prefix not found in context.")

        package_uri: str = self._manifest[f"{ct}:containedInContainer"]["@id"]

        return package_uri.split(":")[-1].split("/")

    def _get_ontology_prefix(self, uri: str) -> Optional[str]:
        """
        Get the ontology prefix from the URI.
        """
        for prefix, onto_uri in self._manifest['@context'].items():
            if isstring(onto_uri) and uri in onto_uri:
                return prefix

        return None

    def __str__(self) -> str:
        return f"{self.title} ({self._manifest['@id']})"
