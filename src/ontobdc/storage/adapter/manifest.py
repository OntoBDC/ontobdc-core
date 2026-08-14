import hashlib
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from ontobdc.storage.adapter.bootstrap import (
    ONTOBDC_DIRECTORY_NAME,
    to_extended_length_path,
)


_IGNORED_MARKER_DIR_NAMES: Set[str] = {
    ONTOBDC_DIRECTORY_NAME,
    ".__onmtobdc__",
}
_DATASET_MARKER_FILE_NAMES: Set[str] = {"dataset.ttl", "nid.ttl"}
_DATASET_LINKSET_DIR_NAME: str = "linkset"
_DATASET_DATAPACKAGE_FILE_NAME: str = "datapackage.json"
_CONTAINER_DATAPACKAGE_FILE_NAME: str = "datapackage.json"


@dataclass(frozen=True)
class ContainerDataPackageSyncResult:
    datapackage_path: Path
    resource_count: int
    local_resource_count: int
    added_resource_count: int
    updated_resource_count: int
    removed_resource_count: int


def _is_dataset_dir(candidate_dir: Path) -> bool:
    marker_dir: Path = candidate_dir / ONTOBDC_DIRECTORY_NAME
    if marker_dir.is_dir():
        for file_name in _DATASET_MARKER_FILE_NAMES:
            if (marker_dir / file_name).is_file():
                return True

    datapackage_file: Path = (
        candidate_dir
        / _DATASET_LINKSET_DIR_NAME
        / _DATASET_DATAPACKAGE_FILE_NAME
    )
    return datapackage_file.is_file()


def list_container_resource_paths(container_path: Path) -> List[str]:
    """List container-owned files, excluding OntoBDC internals and nested datasets."""
    resolved_container_path: Path = container_path.expanduser().resolve()
    if not resolved_container_path.is_dir():
        raise ValueError(f"Container path is not a directory: {resolved_container_path}")

    resource_paths: List[str] = []
    for root, dir_names, file_names in os.walk(
        resolved_container_path,
        topdown=True,
    ):
        root_path: Path = Path(root)
        dir_names[:] = [
            dir_name
            for dir_name in dir_names
            if dir_name not in _IGNORED_MARKER_DIR_NAMES
            and not _is_dataset_dir(root_path / dir_name)
        ]

        for file_name in file_names:
            file_path: Path = root_path / file_name
            relative_path: str = file_path.relative_to(
                resolved_container_path
            ).as_posix()
            if relative_path.strip():
                resource_paths.append(relative_path)

    return sorted(set(resource_paths))


class ContainerDataPackageSynchronizer:
    """Synchronize a container-level Frictionless Data Package descriptor."""

    def sync(self, container_path: Path) -> ContainerDataPackageSyncResult:
        resolved_container_path: Path = container_path.expanduser().resolve()
        if not resolved_container_path.is_dir():
            raise ValueError(
                f"Container path is not a directory: {resolved_container_path}"
            )

        marker_dir: Path = resolved_container_path / ONTOBDC_DIRECTORY_NAME
        marker_dir.mkdir(parents=True, exist_ok=True)
        datapackage_path: Path = marker_dir / _CONTAINER_DATAPACKAGE_FILE_NAME

        descriptor: Dict[str, Any] = self._load_descriptor(datapackage_path)
        original_resources: List[Dict[str, Any]] = self._resource_descriptors(
            descriptor
        )
        resource_paths: List[str] = list_container_resource_paths(
            resolved_container_path
        )
        inventory: Set[str] = set(resource_paths)

        existing_by_path: Dict[str, Dict[str, Any]] = {}
        external_resources: List[Dict[str, Any]] = []
        removed_resource_count: int = 0

        for resource_descriptor in original_resources:
            managed_path: Optional[str] = self._managed_container_path(
                resource_descriptor=resource_descriptor,
                datapackage_path=datapackage_path,
                container_path=resolved_container_path,
            )
            if managed_path is None:
                external_resources.append(dict(resource_descriptor))
                continue

            if managed_path not in inventory or managed_path in existing_by_path:
                removed_resource_count += 1
                continue

            existing_by_path[managed_path] = dict(resource_descriptor)

        synchronized_resources: List[Dict[str, Any]] = []
        added_resource_count: int = 0
        updated_resource_count: int = 0

        for relative_path in resource_paths:
            current_descriptor: Optional[Dict[str, Any]] = existing_by_path.get(
                relative_path
            )
            synchronized_descriptor: Dict[str, Any] = self._build_local_descriptor(
                relative_path=relative_path,
                container_path=resolved_container_path,
                datapackage_path=datapackage_path,
                existing_descriptor=current_descriptor,
            )
            synchronized_resources.append(synchronized_descriptor)

            if current_descriptor is None:
                added_resource_count += 1
            elif synchronized_descriptor != current_descriptor:
                updated_resource_count += 1

        synchronized_resources.extend(external_resources)
        descriptor.setdefault("name", "ontobdc_container")
        descriptor["resources"] = synchronized_resources
        self._write_descriptor(datapackage_path, descriptor)

        return ContainerDataPackageSyncResult(
            datapackage_path=datapackage_path,
            resource_count=len(synchronized_resources),
            local_resource_count=len(resource_paths),
            added_resource_count=added_resource_count,
            updated_resource_count=updated_resource_count,
            removed_resource_count=removed_resource_count,
        )

    def _load_descriptor(self, datapackage_path: Path) -> Dict[str, Any]:
        if not datapackage_path.is_file():
            return {}

        try:
            loaded: Any = json.loads(
                datapackage_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(
                f"Could not read datapackage descriptor: {datapackage_path}"
            ) from exc

        if not isinstance(loaded, dict):
            raise ValueError(
                f"Invalid datapackage descriptor: {datapackage_path}"
            )

        return dict(loaded)

    def _resource_descriptors(
        self,
        descriptor: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raw_resources: Any = descriptor.get("resources", [])
        if raw_resources is None:
            return []
        if not isinstance(raw_resources, list):
            raise ValueError("datapackage.json 'resources' must be a list.")

        return [
            dict(resource)
            for resource in raw_resources
            if isinstance(resource, dict)
        ]

    def _managed_container_path(
        self,
        *,
        resource_descriptor: Dict[str, Any],
        datapackage_path: Path,
        container_path: Path,
    ) -> Optional[str]:
        path_value: Any = resource_descriptor.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            return None

        normalized_path: str = path_value.strip()
        path_candidate: Path = Path(normalized_path).expanduser()
        parsed = urlparse(normalized_path)

        if path_candidate.is_absolute():
            candidate_path: Path = path_candidate.resolve()
        elif parsed.scheme.lower() == "file":
            candidate_path = Path(
                url2pathname(unquote(parsed.path))
            ).expanduser().resolve()
        elif parsed.scheme:
            return None
        else:
            candidate_path = (
                datapackage_path.parent / path_candidate
            ).resolve()

        try:
            return candidate_path.relative_to(container_path).as_posix()
        except ValueError:
            return None

    def _build_local_descriptor(
        self,
        *,
        relative_path: str,
        container_path: Path,
        datapackage_path: Path,
        existing_descriptor: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        file_path: Path = container_path / relative_path
        descriptor: Dict[str, Any] = dict(existing_descriptor or {})
        descriptor_path: str = Path(
            os.path.relpath(file_path, start=datapackage_path.parent)
        ).as_posix()

        descriptor["name"] = str(
            descriptor.get("name") or self._resource_name(relative_path)
        ).strip()
        descriptor["path"] = descriptor_path
        descriptor["bytes"] = to_extended_length_path(file_path).stat().st_size

        file_format: str = file_path.suffix.lower().lstrip(".")
        if file_format:
            descriptor["format"] = file_format
        else:
            descriptor.pop("format", None)

        media_type, _ = mimetypes.guess_type(file_path.name)
        if media_type:
            descriptor["mediatype"] = media_type
        else:
            descriptor.pop("mediatype", None)

        return descriptor

    def _resource_name(self, relative_path: str) -> str:
        path_without_suffix: str = str(Path(relative_path).with_suffix(""))
        normalized_name: str = re.sub(
            r"[^a-z0-9]+",
            "_",
            path_without_suffix.lower(),
        ).strip("_")
        if not normalized_name:
            normalized_name = "resource"
        normalized_name = normalized_name[-80:]
        digest: str = hashlib.sha256(
            relative_path.encode("utf-8")
        ).hexdigest()[:12]
        return f"{normalized_name}_{digest}"

    def _write_descriptor(
        self,
        datapackage_path: Path,
        descriptor: Dict[str, Any],
    ) -> None:
        serialized: str = json.dumps(
            descriptor,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary_path: Path = datapackage_path.with_name(
            f".{datapackage_path.name}.tmp"
        )
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(datapackage_path)
