
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List
from ontobdc.core.adapter.entity import Entity
from ontobdc.cli import config_data, get_config_dir, get_root_dir
from ontobdc.storage.adapter.datapackage import DatapackageSchemaAdapter
from ontobdc.storage.adapter.spreadsheet import MicrosoftSpreadsheetAdapter


def _message_box(level: str, title_type: str, title: str, message: str) -> None:
    try:
        from ontobdc.cli import get_message_box_script
    except Exception:
        print(message)
        return

    script = get_message_box_script()
    if script and os.path.isfile(script):
        subprocess.run(["bash", script, level, title_type, title, message], check=False)
    else:
        print(message)


def _get_arg_value(flag: str) -> Optional[str]:
    args = sys.argv[1:]
    try:
        i = args.index(flag)
        if i + 1 < len(args) and not args[i + 1].startswith("-"):
            return args[i + 1]
    except ValueError:
        pass
    return None


def _resolve_path(raw: str) -> Path:
    raw = (raw or "").strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return Path(raw)
    return Path(os.path.join(get_root_dir(), raw))


def _schema_out_path(resource: Path) -> Path:
    return resource.with_suffix(resource.suffix + ".schema.json")


def _resolve_schema(schema_path: Path) -> Dict[str, Any]:
    data = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("fields"), list):
        return data

    ctx = data.get("@context") if isinstance(data, dict) else None
    if not isinstance(ctx, dict):
        return None

    fields: List[Dict[str, Any]] = []
    for name, v in ctx.items():
        if not isinstance(v, dict):
            continue
        field_type = v.get("@type")
        if not isinstance(field_type, str) or not field_type.strip():
            continue
        fields.append(
            {
                "name": str(name),
                "type": _get_field_type(field_type),
            }
        )
    return {"fields": fields}


def _create_resource(schema: Dict[str, Any], resource: Path) -> None:
    if resource.exists():
        raise RuntimeError(f"Resource already exists: {resource}")
    else:
        resource.parent.mkdir(parents=True, exist_ok=True)

    schema_adapter = DatapackageSchemaAdapter(schema)
    MicrosoftSpreadsheetAdapter.create(resource, schema_adapter)
    _schema_out_path(resource).write_text(
        json.dumps({"fields": schema_adapter.fields}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _entity_framework_enabled() -> bool:
    config_data_content = config_data()
    if not config_data_content:
        return False

    return config_data_content.get("entity", {}).get("framework") == "enabled"


def _resolve_entity_schema(entity_id: str) -> Dict[str, Any]:
    entity_id = (entity_id or "").strip()
    if not entity_id:
        return None

    if entity_id.startswith("urn:entity:"):
        tail = entity_id.split("urn:entity:", 1)[1]
        tail = tail.lstrip("/").strip()
        parts = [p for p in tail.split("/") if p]
        parts = [p.strip().lower() for p in parts]
        if not parts:
            return None
        entity_path = Path(get_config_dir()) / "ontology" / "entity" / Path(*parts)
        entity_path = entity_path.with_suffix(".jsonld")
        if not entity_path.exists():
            return None
        data = json.loads(entity_path.read_text(encoding="utf-8"))
    else:
        return None

    ctx = data.get("@context") if isinstance(data, dict) else None
    if not isinstance(ctx, dict):
        return None

    package_schema: Dict[str, Any] = {"fields": []}
    enum_values: List[str] = []
    for k, v in ctx.items():
        if isinstance(k, str) and k.startswith("status-option:"):
            enum_values.append(k.split(":", 1)[1])

        if not isinstance(v, dict):
            continue
        field_type = v.get("@type")
        if not isinstance(field_type, str) or not field_type.strip():
            continue
        if k in {"code"}:
            continue
        package_schema["fields"].append(
            {
                "name": str(k),
                "type": _get_field_type(field_type),
            }
        )

    for f in package_schema["fields"]:
        if f.get("name") == "status" and enum_values:
            f["constraints"] = {"enum": enum_values}

    return package_schema

def _get_field_type(field_type: str) -> str:
    if 'xsd:string' in field_type:
        return "string"
    if 'xsd:int' in field_type:
        return "integer"
    if 'xsd:float' in field_type:
        return "float"
    if 'xsd:dateTime' in field_type:
        return "datetime"
    if 'xsd:date' in field_type:
        return "date"
    if 'xsd:boolean' in field_type:
        return "boolean"

    return "string"


def _get_field_constraint(entity: Entity, field_name: str) -> Dict[str, Any]:
    constraints: Dict[str, Any] = {}
    field_schema: Dict[str, Any] = entity.fields.get(field_name) or {}

    manifest = getattr(entity, "_manifest", {}) or {}
    node_shape = None
    for v in manifest.values():
        if isinstance(v, dict) and v.get("@type") == "shacl:NodeShape":
            node_shape = v
            break

    prop_shape = None
    if isinstance(node_shape, dict):
        props = node_shape.get("shacl:property")
        if isinstance(props, list):
            target_path = field_schema.get("@id")
            for p in props:
                if isinstance(p, dict) and p.get("@type") == "shacl:PropertyShape":
                    if target_path and p.get("shacl:path") == target_path:
                        prop_shape = p
                        break

    if isinstance(prop_shape, dict):
        min_count = prop_shape.get("shacl:minCount")
        if isinstance(min_count, int) and min_count > 0:
            constraints["required"] = True
        max_count = prop_shape.get("shacl:maxCount")
        if isinstance(max_count, int):
            constraints["maxCount"] = max_count
        enum_values = prop_shape.get("shacl:in")
        if isinstance(enum_values, list) and enum_values:
            constraints["enum"] = list(enum_values)
        return constraints

    raise ValueError(f"SHACL PropertyShape not found for field '{field_name}' (expected shacl:path={field_schema.get('@id')})")


def _validate_resource(schema: Dict[str, Any], resource: Path) -> bool:
    try:
        schema_adapter = DatapackageSchemaAdapter(schema)
    except Exception:
        return False

    return MicrosoftSpreadsheetAdapter.validate(resource, schema_adapter)


def main() -> int:
    file_path = _get_arg_value("--resource")
    schema_path = _get_arg_value("--schema")
    entity_id = _get_arg_value("--entity")

    if not file_path:
        _message_box(
            "RED",
            "Error",
            "Storage Resource",
            "Usage:\n"
            "  ontobdc storage --resource <file_path>\n"
            "  ontobdc storage --resource <file_path> --schema <schema_path>\n"
            "  ontobdc storage --resource <file_path> --entity <entity_id>\n\n"
            "Notes:\n"
            "- If <file_path> does not exist, provide --schema or --entity to create the resource file.\n",
        )
        return 1

    if schema_path and entity_id:
        _message_box(
            "RED",
            "Error",
            "Storage Resource",
            "Invalid arguments: choose only one schema source.\n\n"
            "Use either:\n"
            "  --schema <schema_path>\n"
            "or:\n"
            "  --entity <entity_id>\n",
        )
        return 1

    resource: Path = _resolve_path(file_path)
    if resource is None:
        return 1

    schema_source: Optional[Dict[str, Any]] = None
    if schema_path:
        absolute_schema_path: Optional[Path] = _resolve_path(schema_path)
        schema_source = _resolve_schema(absolute_schema_path) if absolute_schema_path else None
    elif entity_id:
        if not _entity_framework_enabled():
            _message_box(
                "RED",
                "Error",
                "Storage Resource",
                "Entity Framework is not enabled.\n\nRun:\n  ontobdc entity --enable true\n",
            )
            return 1
        schema_source = _resolve_entity_schema(entity_id)

    if resource.exists() and schema_source is None:
        _message_box("GREEN", "Success", "Storage Resource", f"Resource file found:\n{resource}")
        return 0

    if resource.exists() and schema_source is not None:
        _message_box(
            "RED",
            "Error",
            "Storage Resource",
            "Schema handling for an existing resource is not supported yet.\n\n"
            "Use:\n"
            "  ontobdc storage --resource <file_path>\n",
        )
        return 1

    if schema_source is None:
        _message_box(
            "RED",
            "Error",
            "Storage Resource",
            "Resource file does not exist.\n\n"
            "Options:\n"
            f"  1) Create it manually:\n     {resource}\n"
            "  2) Create it from a schema file:\n"
            "     ontobdc storage --resource <file_path> --schema <schema_path>\n"
            "  3) Create it from an entity schema:\n"
            "     ontobdc storage --resource <file_path> --entity <entity_id>\n",
        )
        return 1

    if not isinstance(schema_source, dict) or "fields" not in schema_source:
        _message_box("RED", "Error", "Storage Resource", "Invalid schema source.")
        return 1

    _create_resource(schema_source, resource)
    if not _validate_resource(schema_source, resource):
        _message_box("RED", "Error", "Storage Resource", "Resource file created but is not valid.")
        return 1

    _message_box("GREEN", "Success", "Storage Resource", f"Resource file created:\n{resource}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
