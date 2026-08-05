import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from ontobdc.context.adapter.instance_support import (
    EntityInstanceRepositorySupport,
)
from ontobdc.storage.adapter.bootstrap import (
    get_dataset_storage_file_path,
    get_ontobdc_directory,
)


OBDC: Namespace = Namespace(
    "http://ontobdc.org/ontology/domain/ns.ttl#"
)
DATAPACKAGE_FILE_NAME: str = "datapackage.json"


class DatasetEntityInstanceRepository(EntityInstanceRepositorySupport):
    def __init__(self, *, dataset_path: str, entity: str) -> None:
        self._dataset_path: Path = Path(dataset_path).expanduser().resolve()
        self._entity: str = str(entity).strip()
        if not self._entity:
            raise ValueError("Entity reference is required.")

    @property
    def dataset_path(self) -> Path:
        return self._dataset_path

    @property
    def dataset_metadata_path(self) -> Path:
        return get_dataset_storage_file_path(self._dataset_path)

    @property
    def datapackage_path(self) -> Path:
        return get_ontobdc_directory(
            self._dataset_path
        ) / DATAPACKAGE_FILE_NAME

    def contains_entity(self) -> bool:
        datapackage: Dict[str, Any] = self._load_datapackage()
        resource_descriptors: List[Dict[str, Any]] = (
            self._select_entity_resource_descriptors(datapackage)
        )
        return bool(resource_descriptors)

    def list_instances(self) -> Dict[str, Any]:
        dataset_graph: Graph = self._load_dataset_graph()
        dataset_subject: URIRef = self._resolve_dataset_subject(dataset_graph)
        datapackage: Dict[str, Any] = self._load_datapackage()
        resource_descriptors: List[Dict[str, Any]] = (
            self._select_entity_resource_descriptors(datapackage)
        )
        if not resource_descriptors:
            raise ValueError(
                f"Datapackage '{self.datapackage_path}' does not expose a "
                f"resource for entity '{self._entity}'."
            )

        entity_uri: str = self._resolve_entity_uri(resource_descriptors)
        instances: List[Dict[str, Any]] = self._read_resource_instances(
            resource_descriptors
        )
        return {
            "dataset_uri": str(dataset_subject),
            "dataset_path": str(self._dataset_path),
            "entity": self._local_name(entity_uri or self._entity),
            "entity_uri": entity_uri,
            "resolution": "dataset_datapackage",
            "datapackage_path": str(self.datapackage_path),
            "resource_count": len(resource_descriptors),
            "instance_count": len(instances),
            "instances": instances,
        }

    def _load_dataset_graph(self) -> Graph:
        return self._load_turtle_graph(
            file_path=self.dataset_metadata_path,
            label="dataset metadata",
        )

    def _resolve_dataset_subject(self, dataset_graph: Graph) -> URIRef:
        subjects: List[URIRef] = [
            subject
            for subject in dataset_graph.subjects(
                RDF.type,
                OBDC.EntityDataset,
            )
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError(
                "Dataset metadata must declare exactly one EntityDataset: "
                f"{self.dataset_metadata_path}"
            )
        return subjects[0]

    def _load_datapackage(self) -> Dict[str, Any]:
        if not self.datapackage_path.is_file():
            raise FileNotFoundError(str(self.datapackage_path))

        try:
            descriptor: Any = json.loads(
                self.datapackage_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"Could not read datapackage: {self.datapackage_path}"
            ) from exc

        if not isinstance(descriptor, dict):
            raise ValueError(
                f"Invalid datapackage: {self.datapackage_path}"
            )
        return descriptor

    def _select_entity_resource_descriptors(
        self,
        datapackage: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        for raw_resource in list(datapackage.get("resources") or []):
            if not isinstance(raw_resource, dict):
                continue
            if self._resource_matches_entity(raw_resource):
                selected.append(dict(raw_resource))
        return selected

    def _resource_matches_entity(
        self,
        resource_descriptor: Dict[str, Any],
    ) -> bool:
        resource_entity_uri: str = str(
            resource_descriptor.get("entityUri") or ""
        ).strip()
        resource_entity_identifier: str = str(
            resource_descriptor.get("entityIdentifier") or ""
        ).strip()
        return bool(
            (
                resource_entity_uri
                and self._references_match(
                    resource_entity_uri,
                    self._entity,
                )
            )
            or (
                resource_entity_identifier
                and self._references_match(
                    resource_entity_identifier,
                    self._entity,
                )
            )
        )

    def _resolve_entity_uri(
        self,
        resource_descriptors: List[Dict[str, Any]],
    ) -> str:
        entity_uris: List[str] = []
        for resource_descriptor in resource_descriptors:
            entity_uri: str = str(
                resource_descriptor.get("entityUri") or ""
            ).strip()
            if entity_uri and entity_uri not in entity_uris:
                entity_uris.append(entity_uri)

        if len(entity_uris) > 1:
            raise ValueError(
                "Matched datapackage resources declare different entityUri "
                f"values for '{self._entity}': {entity_uris}"
            )
        if entity_uris:
            return entity_uris[0]
        if ":" in self._entity:
            return self._entity
        return ""

    def _read_resource_instances(
        self,
        resource_descriptors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        instances: List[Dict[str, Any]] = []
        for resource_descriptor in resource_descriptors:
            instances.extend(
                self._read_single_resource_instances(resource_descriptor)
            )
        return instances

    def _read_single_resource_instances(
        self,
        resource_descriptor: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        try:
            from frictionless import Resource
        except ModuleNotFoundError as exc:
            raise ValueError(
                "The 'frictionless' package is required to read entity "
                "resources."
            ) from exc

        runtime_descriptor: Dict[str, Any] = (
            self._build_runtime_resource_descriptor(resource_descriptor)
        )
        resource_name: str = str(
            runtime_descriptor.get("name") or "<unnamed>"
        ).strip()
        try:
            rows: List[Any] = list(Resource(runtime_descriptor).read_rows())
        except Exception as exc:
            raise ValueError(
                f"Could not read entity resource '{resource_name}' from "
                f"dataset '{self._dataset_path}'."
            ) from exc
        return [self._row_to_dict(row) for row in rows]

    def _build_runtime_resource_descriptor(
        self,
        resource_descriptor: Dict[str, Any],
    ) -> Dict[str, Any]:
        runtime_descriptor: Dict[str, Any] = dict(resource_descriptor)
        if "path" in runtime_descriptor:
            runtime_descriptor["path"] = self._resolve_resource_path_value(
                runtime_descriptor["path"]
            )
        return runtime_descriptor

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
            (self.datapackage_path.parent / Path(raw_path))
            .expanduser()
            .resolve()
        )

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, Mapping):
            return dict(row)

        for method_name in ("to_dict", "to_mapping"):
            method = getattr(row, method_name, None)
            if not callable(method):
                continue
            value: Any = method()
            if isinstance(value, Mapping):
                return dict(value)

        try:
            return dict(row)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Could not convert entity resource row to a mapping: "
                f"{row!r}"
            ) from exc
