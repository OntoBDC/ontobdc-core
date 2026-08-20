import hashlib
import json
import mimetypes
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, FrozenSet, List, Optional, Set
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from frictionless import Resource, System, system as frictionless_system

from ontobdc.storage.adapter.bootstrap import (
    StorageLayoutConstants,
    StoragePathStatHelper,
)


_MISSING_STAT_RESULT: os.stat_result = os.stat_result(
    (
        0,  # st_mode
        0,  # st_ino
        0,  # st_dev
        0,  # st_nlink
        0,  # st_uid
        0,  # st_gid
        0,  # st_size <---- the only attribute we actually consume downstream
        0.0,  # st_atime
        0.0,  # st_mtime
        0.0,  # st_ctime
    )
)


@dataclass(frozen=True)
class ContainerDataPackageSyncResult:
    datapackage_path: Path
    resource_count: int
    local_resource_count: int
    added_resource_count: int
    updated_resource_count: int
    removed_resource_count: int


class FrictionlessFormatRegistry:
    """Single source of truth for frictionless-supported file formats.

    Format support is resolved by probing :meth:`frictionless.System.create_parser`
    directly — the exact same path frictionless itself uses at runtime when it
    actually reads a file. Answers are cached per-process (via class-level
    :func:`functools.lru_cache`) so each distinct format is probed only once,
    which keeps the hot path inside container walking effectively free.

    The candidate pool stored in :attr:`CANDIDATES` exists only to pre-warm the
    cache on the first call to :meth:`get_supported_formats` so plugins that
    ship with frictionless by default are already known without any cache miss
    during the normal ``os.walk`` of a container. Plugins registered later are
    still detected through :meth:`supports` and do not require code changes.
    """

    CANDIDATES: ClassVar[FrozenSet[str]] = frozenset({
        "csv", "tsv", "txt", "psv",
        "xlsx", "xls", "xlsm", "xlsb",
        "ods", "numbers",
        "json", "ndjson", "jsonl", "geojson",
        "parquet", "pq", "orc", "feather", "avro",
        "yaml", "yml", "toml",
        "html", "htm", "xml",
        "sav", "zsav", "por", "sas7bdat", "xpt", "dta",
        "sql", "sqlite", "sqlite3", "db",
        "md", "markdown", "rst",
        "pdf", "docx", "doc", "odt", "pptx", "ppt",
        "shp", "dbf", "kml", "gml", "gpx",
        "zip", "gz", "tar", "bz2", "xz", "7z", "rar",
        "log", "ini", "cfg",
    })

    @classmethod
    @lru_cache(maxsize=None)
    def supports(cls, file_format: str) -> bool:
        """Return True iff frictionless has a registered parser for ``file_format``."""
        normalized: str = str(file_format or "").strip().lower()
        if not normalized:
            return False
        try:
            resource: Resource = Resource(path="dummy.bin", format=normalized)
            active_system: System = frictionless_system or System()
            active_system.create_parser(resource)
        except Exception:
            return False
        return True

    @classmethod
    def get_supported_formats(cls) -> FrozenSet[str]:
        """Return the set of file extensions frictionless can actually parse."""
        return frozenset(fmt for fmt in cls.CANDIDATES if cls.supports(fmt))


class ContainerDataPackageSynchronizer:
    """Synchronize a container-level Frictionless Data Package descriptor.

    All directory traversal, descriptor build-up, and format gating lives
    inside this class. No module-level function participates in any decision
    — the thin module-level symbols exported below are purely backwards
    compatible aliases that delegate to methods on this class.
    """

    _IGNORED_MARKER_DIR_NAMES: ClassVar[Set[str]] = {
        StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME,
    }
    _BLOCKED_FILE_EXTENSIONS: ClassVar[FrozenSet[str]] = frozenset({
        "ini",
        "cfg",
        "conf",
        "log",
        "bak",
        "tmp",
        "temp",
        "swp",
        "crdownload",
        "part",
        "lock",
    })
    _BLOCKED_FILE_BASENAMES: ClassVar[FrozenSet[str]] = frozenset({
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
        "index.html",
        "onto-file-viewer.html",
    })
    _DATASET_MARKER_FILE_NAMES: ClassVar[Set[str]] = {"dataset.ttl", "nid.ttl"}
    _DATASET_LINKSET_DIR_NAME: ClassVar[str] = "linkset"
    _DATASET_DATAPACKAGE_FILE_NAME: ClassVar[str] = "datapackage.json"
    _CONTAINER_DATAPACKAGE_FILE_NAME: ClassVar[str] = "datapackage.json"

    @classmethod
    def is_file_blocked_from_publication(cls, file_name: str) -> bool:
        """Return ``True`` when *file_name* must not appear in any
        user-facing surface (RO-Crate ``hasPart``, file tree tile,
        per-file display entities, datapackage resource lists etc.).

        Blocks are matched against both the lower-cased base name
        (for dotfiles like ``.DS_Store`` or hidden metadata such as
        ``Thumbs.db``) and the lower-cased extension without the
        leading dot (for ``*.ini``, ``*.bak`` and similar temporary
        or system artefacts).
        """
        normalized_name: str = Path(file_name).name.lower()
        if normalized_name in cls._BLOCKED_FILE_BASENAMES:
            return True
        suffix: str = Path(file_name).suffix.lower().lstrip(".")
        return bool(suffix) and suffix in cls._BLOCKED_FILE_EXTENSIONS

    @classmethod
    def _is_dataset_dir(cls, candidate_dir: Path) -> bool:
        marker_dir: Path = candidate_dir / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
        if marker_dir.is_dir():
            for file_name in cls._DATASET_MARKER_FILE_NAMES:
                if (marker_dir / file_name).is_file():
                    return True

        datapackage_file: Path = (
            candidate_dir
            / cls._DATASET_LINKSET_DIR_NAME
            / cls._DATASET_DATAPACKAGE_FILE_NAME
        )
        return datapackage_file.is_file()

    @classmethod
    def _iter_container_file_paths(cls, container_path: Path) -> List[Path]:
        """Walk the container directory yielding every on-disk file path.

        Excludes only the OntoBDC marker directory and nested datasets
        (paths reserved for the platform itself).  Callers layer additional
        filters on top (e.g. frictionless-format gating for a Data Package or
        no filter at all for the presentation file tree).
        """
        resolved_container_path: Path = container_path.expanduser().resolve()
        if not resolved_container_path.is_dir():
            raise ValueError(
                f"Container path is not a directory: {resolved_container_path}"
            )

        file_paths: List[Path] = []
        for root, dir_names, file_names in os.walk(
            resolved_container_path,
            topdown=True,
        ):
            root_path: Path = Path(root)
            dir_names[:] = [
                dir_name
                for dir_name in dir_names
                if dir_name not in cls._IGNORED_MARKER_DIR_NAMES
                and not cls._is_dataset_dir(root_path / dir_name)
            ]

            for file_name in file_names:
                file_paths.append(root_path / file_name)

        return file_paths

    @classmethod
    def list_resource_paths(cls, container_path: Path) -> List[str]:
        """List container-owned files whose format is frictionless-compatible.

        Excludes OntoBDC internals, nested datasets, and files whose
        extension frictionless doesn't have a registered parser for.
        """
        resource_paths: List[str] = []
        resolved_container_path: Path = container_path.expanduser().resolve()
        for file_path in cls._iter_container_file_paths(container_path):
            file_format: str = file_path.suffix.lower().lstrip(".")
            if not FrictionlessFormatRegistry.supports(file_format):
                continue
            relative_path: str = file_path.relative_to(
                resolved_container_path
            ).as_posix()
            if relative_path.strip():
                resource_paths.append(relative_path)

        return sorted(set(resource_paths))

    @classmethod
    def list_container_file_paths(cls, container_path: Path) -> List[str]:
        """List every container-owned file as POSIX relative paths.

        Used for the presentation file tree and other places that must reflect
        *all* on-disk content, not just frictionless-tabular resources.
        Same OntoBDC-internal and nested-dataset exclusions as
        ``list_resource_paths`` apply, plus a centralised publication block
        list (dotfiles, hidden system metadata, temporary artefacts) via
        ``is_file_blocked_from_publication``. PDFs, images, CAD files, IFC
        payloads, documents etc. are still included so the UI surface's
        FILES tree matches what's actually in the container.
        """
        resolved_container_path: Path = container_path.expanduser().resolve()
        relative_paths: List[str] = [
            file_path.relative_to(resolved_container_path).as_posix()
            for file_path in cls._iter_container_file_paths(container_path)
            if not cls.is_file_blocked_from_publication(file_path.name)
        ]
        return sorted({p for p in relative_paths if p.strip()})

    def sync(self, container_path: Path) -> ContainerDataPackageSyncResult:
        resolved_container_path: Path = container_path.expanduser().resolve()
        if not resolved_container_path.is_dir():
            raise ValueError(
                f"Container path is not a directory: {resolved_container_path}"
            )

        marker_dir: Path = resolved_container_path / StorageLayoutConstants.ONTOBDC_DIRECTORY_NAME
        marker_dir.mkdir(parents=True, exist_ok=True)
        datapackage_path: Path = (
            marker_dir / self._CONTAINER_DATAPACKAGE_FILE_NAME
        )

        descriptor: Dict[str, Any] = self._load_descriptor(datapackage_path)
        original_resources: List[Dict[str, Any]] = self._resource_descriptors(
            descriptor
        )
        resource_paths: List[str] = self.list_resource_paths(
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

            resource_format: str = str(
                resource_descriptor.get("format", "")
            ).strip().lower()
            if not FrictionlessFormatRegistry.supports(resource_format):
                removed_resource_count += 1
                continue

            if managed_path not in inventory or managed_path in existing_by_path:
                removed_resource_count += 1
                continue

            existing_by_path[managed_path] = dict(resource_descriptor)

        synchronized_resources: List[Dict[str, Any]] = []
        added_resource_count: int = 0
        updated_resource_count: int = 0

        for relative_path in resource_paths:
            file_format: str = Path(relative_path).suffix.lower().lstrip(".")
            if not FrictionlessFormatRegistry.supports(file_format):
                continue
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
        descriptor["bytes"] = (
            (StoragePathStatHelper.safe_stat(file_path) or _MISSING_STAT_RESULT).st_size
        )

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

