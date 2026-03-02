
import json
from pathlib import Path
from typing import Any, Dict, Set, Type
import importlib
from ontobdc.core.domain.schema.entity import SchemaEntity


SCHEMA_PATH = Path(
    "ontobdc/module/resource/schema/entity/resource_file_schema.json"
)


class EntityFactory:
    _cache: Dict[str, Any] = {}

    @classmethod
    def _load_schema(cls) -> Dict[str, Any]:
        if not cls._cache:
            text = SCHEMA_PATH.read_text(encoding="utf-8")
            cls._cache = json.loads(text)
        return cls._cache

    @staticmethod
    def _port_to_entity_name(entity_port: Type[object]) -> str:
        name = entity_port.__name__
        if name.endswith("Port"):
            name = name[:-4]
        if not name:
            raise ValueError("Invalid entity port class name")
        return name[0].lower() + name[1:]

    @staticmethod
    def _required_params(entity_port: Type[object], entity_name: str) -> Set[str]:
        value = getattr(entity_port, "RUNTIME_FIELDS", None)
        if isinstance(value, (set, list, tuple)):
            return set(value)
        return set()

    @classmethod
    def make(cls, entity_port: Type[object], **runtime: Any) -> SchemaEntity:
        schema = cls._load_schema()
        entity_name = cls._port_to_entity_name(entity_port)
        payload = schema.get(entity_name)
        if not isinstance(payload, dict):
            raise KeyError(f"Entity '{entity_name}' not found in resource file schema")

        required = cls._required_params(entity_port, entity_name)
        missing = [name for name in required if name not in runtime]
        if missing:
            missing_str = ", ".join(sorted(missing))
            raise ValueError(f"Missing required parameters for '{entity_name}': {missing_str}")

        entity = SchemaEntity(name=entity_name, payload=payload)
        for name, value in runtime.items():
            setattr(entity, name, value)
        adapter_map = getattr(entity_port, "ADAPTERS", None)
        filesystem = runtime.get("filesystem")
        adapter_path = None
        if isinstance(adapter_map, dict) and filesystem in adapter_map:
            adapter_path = adapter_map.get(filesystem)
        if not adapter_path:
            adapter_path = getattr(entity_port, "ADAPTER_CLASS", None)
        if isinstance(adapter_path, str) and adapter_path:
            module_name, class_name = adapter_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            adapter_cls = getattr(module, class_name)
            return adapter_cls(entity, **runtime)
        return entity
