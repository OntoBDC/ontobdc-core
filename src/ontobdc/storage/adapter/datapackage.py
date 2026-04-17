

from typing import Any, Dict, List
from ontobdc.storage.core.port.spreadsheet import TableSchemaPort


class DatapackageSchemaAdapter(TableSchemaPort):
    def __init__(self, schema: Dict[str, Any]) -> None:
        if not self._is_valid_schema(schema):
            raise ValueError

        self._schema = schema

    @property
    def fields(self) -> List[Dict[str, Any]]:
        fields = self._schema.get("fields")
        if not isinstance(fields, list):
            return []
        out: List[Dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict):
                continue
            name = f.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            out.append(f)
        return out

    def _is_valid_schema(self, schema: Dict[str, Any]) -> bool:
        if not isinstance(schema, dict):
            return False

        if "fields" not in schema.keys():
            return False

        fields = schema.get("fields")
        if not isinstance(fields, list):
            return False

        for f in fields:
            if not isinstance(f, dict):
                return False

            name = f.get("name")
            if not isinstance(name, str) or not name.strip():
                return False

            type = f.get("type")
            if not isinstance(type, str) or not type.strip():
                return False

        return True