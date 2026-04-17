
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
        dcterms: str = self.get_ontology_prefix(str(DCTERMS))
        return self._manifest[f"{dcterms}:title"]

    @property
    def description(self) -> str:
        dcterms: str = self.get_ontology_prefix(str(DCTERMS))
        return self._manifest[f"{dcterms}:description"]

    @property
    def package(self) -> List[str]:
        """
        Get the package of the entity.
        """
        ct: Optional[str] = self.get_ontology_prefix("https://standards.iso.org/iso/21597/-1/ed-1/en/Container#")
        if ct is None:
            raise ValueError("Container prefix not found in context.")

        package_uri: str = self._manifest[f"{ct}:containedInContainer"]["@id"]

        return package_uri.split(":")[-1].split("/")

    @property
    def fields(self) -> Dict[str, Any]:
        """
        Get the fields of the entity.
        """
        fields: Dict[str, Any] = {}
        for field_name, field in self._manifest['@context'].items():
            if isinstance(field, dict) and '@id' in field.keys() and '@type' in field.keys():
                fields[field_name] = field

        return fields

    def get_uri(self, prefix: str) -> Optional[str]:
        if prefix in self._manifest['@context']:
            return self._manifest['@context'][prefix]

        return None

    def get_ontology_prefix(self, uri: str) -> Optional[str]:
        """
        Get the ontology prefix from the URI.
        """
        for prefix, onto_uri in self._manifest['@context'].items():
            if isstring(onto_uri) and uri in onto_uri:
                return prefix

        return None

    def get_objects_from_prefix(self, prefix: str) -> List[Dict[str, Any]]:
        """
        Get the objects from the prefix.
        """
        prefixed:  List[Dict[str, Any]] = []
        for key, value in self._manifest['@context'].items():
            if key.startswith(f"{prefix}:"):
                prefixed.append({value: key.split(f"{prefix}:")[-1]})

        return prefixed

    def __str__(self) -> str:
        return f"{self.title} ({self._manifest['@id']})"
