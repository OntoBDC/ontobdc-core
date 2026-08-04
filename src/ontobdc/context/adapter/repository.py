import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Mapping, Type

from ontobdc.shared.adapter.entity_workbook import EntityWorkbookAdapter, EntityWorkbookField
from ontobdc.shared.domain.port.resource import FileResourcePort


class LocalContextFileResource(FileResourcePort):
    def __init__(self, file_path: Path):
        self._path: Path = Path(file_path).expanduser().resolve()

    @property
    def name(self) -> str:
        return self._path.name

    @property
    def container(self) -> None:
        return None

    @property
    def dataset(self) -> None:
        return None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def mimetype(self) -> str:
        detected_mimetype, _ = mimetypes.guess_type(str(self._path))
        return detected_mimetype or "application/octet-stream"

    @property
    def content(self) -> Any:
        if not self._path.exists():
            raise FileNotFoundError(str(self._path))

        if self.is_text():
            return self._path.read_text(encoding="utf-8")

        return self._path.read_bytes()

    def exists(self) -> bool:
        return self._path.exists()

    def is_text(self) -> bool:
        return (
            self._path.suffix.lower() in {".txt", ".md", ".json", ".ttl", ".yaml", ".yml"}
            or self.mimetype.startswith("text/")
            or self.mimetype in {"application/json", "application/ld+json"}
        )

    def is_binary(self) -> bool:
        return not self.is_text()

    def is_multimedia(self) -> bool:
        return self.mimetype.startswith(("image/", "audio/", "video/"))

    def is_dict(self) -> bool:
        return self._path.suffix.lower() == ".json"

    def rename(self, dst: Path) -> None:
        self._path = self._path.rename(dst)

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self._path),
            "uri": self._path.as_uri(),
            "mimetype": self.mimetype,
        }

    def write(self, dataset: Any) -> None:
        raise NotImplementedError("LocalContextFileResource.write is not supported.")


class EntityLearningStepRepository:
    FILE_TYPES: List[str] = ["yaml", "yml", "jsonld", "json", "ttl", "md", "txt", "rdf", "xml"]

    def __init__(self, root_path: str, source_path: str) -> None:
        self._root_path: Path = Path(root_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Learning source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "learning" / "entity" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def source_hash(self) -> str:
        return self._source_hash

    @property
    def step_dir(self) -> Path:
        return self._step_dir

    def reload(self, state: Any) -> LocalContextFileResource:
        state_value: str = str(state.value)
        if state_value == "__undefined__":
            return LocalContextFileResource(self._source_path)

        for file_type in self.FILE_TYPES:
            candidate_path: Path = self._step_dir / f"{state_value}.{file_type}"
            if candidate_path.exists():
                return LocalContextFileResource(candidate_path)

        raise FileNotFoundError(f"Learning step not found for '{state_value}' in '{self._step_dir}'.")

    def save(self, state: Any, resource: LocalContextFileResource) -> None:
        extension: str = resource.path.suffix.lstrip(".").strip().lower()
        if extension not in self.FILE_TYPES:
            extension = "json"
            target_path: Path = self._step_dir / f"{state.value}.{extension}"
            target_path.write_text(
                json.dumps(resource.to_json(), ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return

        target_path = self._step_dir / f"{state.value}.{extension}"
        if resource.path != target_path:
            if resource.is_text():
                target_path.write_text(str(resource.content), encoding="utf-8")
            else:
                target_path.write_bytes(resource.content)

    def exists(self, state: Any) -> bool:
        if str(state.value) == "__undefined__":
            return True

        for file_type in self.FILE_TYPES:
            if (self._step_dir / f"{state.value}.{file_type}").exists():
                return True
        return False

    def delete(self, state: Any) -> None:
        for candidate_path in self._step_dir.glob(f"{state.value}.*"):
            if candidate_path.is_file():
                candidate_path.unlink()

    def all(self, state_class: Type[Any]) -> List[Any]:
        states: List[Any] = []
        for candidate_path in self._step_dir.iterdir():
            if not candidate_path.is_file():
                continue
            if candidate_path.suffix.lstrip(".").lower() not in self.FILE_TYPES:
                continue
            try:
                states.append(state_class(candidate_path.stem))
            except Exception:
                continue
        return states

    def write_text_file(
        self,
        state: Any,
        content: str,
        file_type: str = "txt",
        encoding: str = "utf-8",
    ) -> Path:
        target_path: Path = self._step_dir / f"{state.value}.{file_type}"
        target_path.write_text(content, encoding=encoding)
        return target_path


class EntityAnalysisStepRepository(EntityLearningStepRepository):
    def __init__(self, root_path: str, source_path: str) -> None:
        self._root_path: Path = Path(root_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Analysis source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "analysis" / "entity" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)


class DocumentImportStepRepository(EntityLearningStepRepository):
    def __init__(self, container_path: str, source_path: str) -> None:
        self._root_path: Path = Path(container_path).expanduser().resolve()
        self._source_path: Path = Path(source_path).expanduser().resolve()
        if not self._source_path.exists() or not self._source_path.is_file():
            raise FileNotFoundError(f"Import source not found: {self._source_path}")

        self._source_hash: str = hashlib.sha256(self._source_path.read_bytes()).hexdigest()
        self._step_dir: Path = (
            self._root_path / ".__ontobdc__" / "etl" / "import" / "document" / self._source_hash
        )
        self._step_dir.mkdir(parents=True, exist_ok=True)


class EntityContainerInstanceRepository:
    def __init__(
        self,
        *,
        container_path: str,
        facade: Dict[str, Any],
    ) -> None:
        self._container_path: Path = Path(container_path).expanduser().resolve()
        self._facade: Dict[str, Any] = dict(facade)
        self._datapackage_path: Path = (
            self._container_path / ".__ontobdc__" / "datapackage.json"
        )
        self._workbook_adapter: EntityWorkbookAdapter = EntityWorkbookAdapter()

    def list_instances(self) -> Dict[str, Any]:
        resource_descriptors: List[Dict[str, Any]] = (
            self._load_entity_resource_descriptors()
        )
        if not resource_descriptors:
            return self._list_legacy_workbook_instances()

        instances: List[Dict[str, Any]] = []
        resources: List[Dict[str, Any]] = []
        for resource_descriptor in resource_descriptors:
            resource_instances: List[Dict[str, Any]] = (
                self._read_resource_instances(resource_descriptor)
            )
            instances.extend(resource_instances)
            resources.append(
                self._resource_payload(
                    resource_descriptor=resource_descriptor,
                    instance_count=len(resource_instances),
                )
            )

        workbook_resource: Dict[str, Any] = next(
            (
                resource
                for resource in resources
                if str(resource.get("format") or "").lower() in {"xls", "xlsx"}
            ),
            {},
        )
        return {
            "entity": str(self._facade.get("entity_name") or "").strip(),
            "resolution": "datapackage",
            "datapackage_path": str(self._datapackage_path),
            "resource_count": len(resources),
            "resources": resources,
            "workbook_path": str(workbook_resource.get("resolved_path") or ""),
            "worksheet_name": str(workbook_resource.get("worksheet_name") or ""),
            "instance_count": len(instances),
            "instances": instances,
        }

    def _load_entity_resource_descriptors(self) -> List[Dict[str, Any]]:
        if not self._datapackage_path.is_file():
            return []

        try:
            descriptor: Any = json.loads(
                self._datapackage_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"Could not read datapackage descriptor: {self._datapackage_path}"
            ) from exc

        if not isinstance(descriptor, dict):
            raise ValueError(
                f"Invalid datapackage descriptor: {self._datapackage_path}"
            )

        entity_uri: str = str(self._facade.get("entity_uri") or "").strip()
        entity_identifier: str = str(
            self._facade.get("entity_identifier") or ""
        ).strip()

        matches: List[Dict[str, Any]] = []
        for raw_resource in list(descriptor.get("resources") or []):
            if not isinstance(raw_resource, dict):
                continue

            resource_entity_uri: str = str(
                raw_resource.get("entityUri") or ""
            ).strip()
            resource_entity_identifier: str = str(
                raw_resource.get("entityIdentifier") or ""
            ).strip()
            uri_matches: bool = bool(
                entity_uri
                and resource_entity_uri
                and resource_entity_uri == entity_uri
            )
            identifier_matches: bool = bool(
                entity_identifier
                and resource_entity_identifier
                and resource_entity_identifier == entity_identifier
            )
            if uri_matches or identifier_matches:
                matches.append(dict(raw_resource))

        return matches

    def _read_resource_instances(
        self,
        resource_descriptor: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        try:
            from frictionless import Resource
        except ModuleNotFoundError as exc:
            raise ValueError(
                "The 'frictionless' package is required to read entity resources."
            ) from exc

        runtime_descriptor: Dict[str, Any] = dict(resource_descriptor)
        if "path" in runtime_descriptor:
            runtime_descriptor["path"] = self._resolve_resource_path_value(
                runtime_descriptor["path"]
            )

        resource_name: str = str(
            runtime_descriptor.get("name") or "<unnamed>"
        ).strip()
        try:
            rows: List[Any] = list(Resource(runtime_descriptor).read_rows())
        except Exception as exc:
            raise ValueError(
                f"Could not read entity resource '{resource_name}'."
            ) from exc

        return [self._row_to_dict(row) for row in rows]

    def _resolve_resource_path_value(self, path_value: Any) -> Any:
        if isinstance(path_value, list):
            return [
                self._resolve_resource_path_value(item)
                for item in path_value
            ]

        raw_path: str = str(path_value or "").strip()
        if not raw_path or "://" in raw_path:
            return raw_path

        return str(
            (self._datapackage_path.parent / Path(raw_path))
            .expanduser()
            .resolve()
        )

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, Mapping):
            return dict(row)

        for method_name in ("to_dict", "to_mapping"):
            method = getattr(row, method_name, None)
            if callable(method):
                value: Any = method()
                if isinstance(value, Mapping):
                    return dict(value)

        try:
            return dict(row)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Could not convert entity resource row to a mapping: {row!r}"
            ) from exc

    def _resource_payload(
        self,
        *,
        resource_descriptor: Dict[str, Any],
        instance_count: int,
    ) -> Dict[str, Any]:
        path_value: Any = resource_descriptor.get("path")
        resolved_path: Any = (
            self._resolve_resource_path_value(path_value)
            if path_value is not None
            else ""
        )
        dialect: Dict[str, Any] = dict(
            resource_descriptor.get("dialect") or {}
        )
        excel_dialect: Dict[str, Any] = dict(dialect.get("excel") or {})
        resource_format: str = str(
            resource_descriptor.get("format")
            or self._path_format(resolved_path)
        ).strip()

        return {
            "name": str(resource_descriptor.get("name") or "").strip(),
            "path": path_value,
            "resolved_path": resolved_path,
            "format": resource_format,
            "worksheet_name": str(excel_dialect.get("sheet") or "").strip(),
            "entity_uri": str(resource_descriptor.get("entityUri") or "").strip(),
            "entity_identifier": str(
                resource_descriptor.get("entityIdentifier") or ""
            ).strip(),
            "facade_uri": str(resource_descriptor.get("facadeUri") or "").strip(),
            "instance_uri_template": str(
                resource_descriptor.get("instanceUriTemplate") or ""
            ).strip(),
            "instance_count": instance_count,
        }

    def _path_format(self, path_value: Any) -> str:
        if isinstance(path_value, list):
            if not path_value:
                return ""
            return Path(str(path_value[0])).suffix.lstrip(".").lower()
        return Path(str(path_value or "")).suffix.lstrip(".").lower()

    def _list_legacy_workbook_instances(self) -> Dict[str, Any]:
        workbook_contract: Dict[str, Any] = self._build_workbook_contract()
        instances: List[Dict[str, Any]] = self._workbook_adapter.read(
            workbook_path=Path(
                str(workbook_contract["workbook_path"])
            ).expanduser().resolve(),
            worksheet_name=str(workbook_contract["worksheet_name"]),
            fields=list(workbook_contract["fields"]),
        )
        resource: Dict[str, Any] = {
            "name": str(self._facade.get("entity_identifier") or "").strip(),
            "path": str(workbook_contract["workbook_path"]),
            "resolved_path": str(workbook_contract["workbook_path"]),
            "format": "xlsx",
            "worksheet_name": str(workbook_contract["worksheet_name"]),
            "entity_uri": str(self._facade.get("entity_uri") or "").strip(),
            "entity_identifier": str(
                self._facade.get("entity_identifier") or ""
            ).strip(),
            "facade_uri": str(self._facade.get("facade_uri") or "").strip(),
            "instance_uri_template": "",
            "instance_count": len(instances),
        }

        return {
            "entity": str(self._facade.get("entity_name") or "").strip(),
            "resolution": "legacy_convention",
            "datapackage_path": str(self._datapackage_path),
            "resource_count": 1,
            "resources": [resource],
            "workbook_path": str(workbook_contract["workbook_path"]),
            "worksheet_name": str(workbook_contract["worksheet_name"]),
            "instance_count": len(instances),
            "instances": instances,
        }

    def _build_workbook_contract(self) -> Dict[str, Any]:
        entity_name: str = str(self._facade.get("entity_name") or "").strip()
        entity_identifier: str = str(
            self._facade.get("entity_identifier") or ""
        ).strip()
        if not entity_name or not entity_identifier:
            raise ValueError("The resolved entity facade is incomplete.")

        fields: List[EntityWorkbookField] = [
            EntityWorkbookField(
                name=str(field["name"]),
                field_type=self._frictionless_type(
                    str(field.get("datatype", "string"))
                ),
            )
            for field in list(self._facade.get("fields") or [])
            if str(field.get("name") or "").strip()
        ]
        if not fields:
            raise ValueError(
                f"The entity facade does not expose any workbook fields: {entity_name}"
            )

        output_dir: Path = self._container_path / "payload" / "document"
        workbook_name: str = f"{entity_identifier}.xlsx"
        worksheet_name: str = entity_name[:31]

        return {
            "workbook_path": output_dir / workbook_name,
            "worksheet_name": worksheet_name,
            "fields": fields,
        }

    def _frictionless_type(self, datatype: str) -> str:
        return {
            "any_uri": "string",
            "boolean": "boolean",
            "date": "date",
            "date_time": "datetime",
            "dateTime": "datetime",
            "decimal": "number",
            "double": "number",
            "float": "number",
            "integer": "integer",
        }.get(datatype, "string")
