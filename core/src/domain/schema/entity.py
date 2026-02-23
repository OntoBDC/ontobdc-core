
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


SCHEMA_PATH = Path(
    "ontobdc/resource/data/schema/file/class/resource_file_class_schema.json"
)


class SchemaEntity:
    def __init__(self, name: str, payload: Dict[str, Any]) -> None:
        self._name = name
        self._payload = payload

    @property
    def name(self) -> str:
        return self._name

    @property
    def identifier(self) -> Optional[str]:
        return self._payload.get("http://purl.org/dc/terms/identifier")

    @property
    def properties(self) -> Dict[str, List[str]]:
        props = self._payload.get("properties")
        if isinstance(props, dict):
            return props
        return {}

    @property
    def type_definition(self) -> Optional[str]:
        type_block = self._payload.get("type")
        if isinstance(type_block, dict):
            value = type_block.get("definition")
            if isinstance(value, str):
                return value
        return None

    @property
    def type_maps_to(self) -> List[str]:
        type_block = self._payload.get("type")
        if isinstance(type_block, dict):
            value = type_block.get("mapsTo")
            if isinstance(value, list):
                return [v for v in value if isinstance(v, str)]
        return []

    @property
    def label(self) -> Optional[str]:
        key = "http://www.w3.org/2000/01/rdf-schema#label"
        values = self.properties.get(key)
        if not values:
            return None
        first = values[0]
        if isinstance(first, str):
            return first
        return None

    def is_a(self, type: str) -> bool:
        if type == self.identifier:
            return True

        if type == self.type_definition:
            return True

        if type in self.type_maps_to:
            return True

        return False

    def __repr__(self) -> str:
        ident = self.identifier or self._name
        return f"<{ident}>"


# class ResourceFileClassSchemaService:
#     def __init__(self, schema_path: Optional[Path] = None) -> None:
#         self._schema_path = schema_path or SCHEMA_PATH
#         self._cache: Optional[Dict[str, Any]] = None

#     def _load_schema(self) -> Dict[str, Any]:
#         if self._cache is None:
#             text = self._schema_path.read_text(encoding="utf-8")
#             self._cache = json.loads(text)
#         return self._cache

#     def get_entity(self, name: str) -> SchemaEntity:
#         schema = self._load_schema()
#         payload = schema.get(name)
#         if not isinstance(payload, dict):
#             raise KeyError(f"Entity '{name}' not found in resource file class schema")
#         return SchemaEntity(name=name, payload=payload)
