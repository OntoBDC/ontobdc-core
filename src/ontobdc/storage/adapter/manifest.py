import os
import re
import json
from typing import Any, ClassVar, Dict, FrozenSet, List, Optional, Set, Tuple
import hashlib
from pathlib import Path
from functools import lru_cache
import mimetypes
from dataclasses import dataclass
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
    def supports(cls, file_format: Optional[str]) -> bool:
        """Return True iff frictionless has a registered parser for ``file_format``."""
        if file_format is None:
            raise ValueError("FrictionlessFormatRegistry.supports requires a non-None file_format.")
        normalized: str = str(file_format).strip().lower()
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

    _SAFE_RELATIVE_PATH_LENGTH_LIMIT: ClassVar[int] = 512
    _MACOS_MAXPATH: ClassVar[int] = 1024

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
                raw_path_value: Any = resource_descriptor.get("path")
                is_external_url: bool = False
                if isinstance(raw_path_value, str):
                    stripped_path: str = raw_path_value.strip()
                    if stripped_path:
                        external_parsed = urlparse(stripped_path)
                        external_scheme: str = external_parsed.scheme.lower()
                        if external_scheme and external_scheme not in {"", "file"}:
                            is_external_url = True
                if is_external_url:
                    external_resources.append(dict(resource_descriptor))
                continue

            if "format" not in resource_descriptor:
                raise ValueError(
                    "ManifestDescriptorBuilder: resource_descriptor is missing required 'format' key."
                )
            resource_format_raw: Any = resource_descriptor["format"]
            if resource_format_raw is None:
                raise ValueError(
                    "ManifestDescriptorBuilder: resource_descriptor 'format' value is None."
                )
            resource_format: str = str(resource_format_raw).strip().lower()
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
        """Load a descriptor, initializing resources only for a new package."""
        if not datapackage_path.exists():
            return {"resources": []}

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
        if "resources" not in descriptor:
            raise ValueError("datapackage.json is missing the required 'resources' top-level key.")
        raw_resources: Any = descriptor["resources"]
        if raw_resources is None:
            raise ValueError("datapackage.json 'resources' top-level key is None.")
        if not isinstance(raw_resources, list):
            raise ValueError("datapackage.json 'resources' must be a list.")

        return [
            dict(resource)
            for resource in raw_resources
            if isinstance(resource, dict)
        ]

    @staticmethod
    def _basename_from_any_path(raw_path: Any) -> str:
        """Extract the trailing file name from an arbitrary path-like string
        without ever joining the raw value to any directory.

        Paths stored in previously-corrupted ``datapackage.json`` descriptors
        can exceed the OS ``MAXPATH`` length (``Errno 63 ENAMETOOLONG`` on
        macOS) and will raise from ``Path(...)`` construction or the ``/``
        join operator if the raw bytes are ever fed through ``pathlib``.
        Stripping the basename via plain string ``rfind`` keeps the
        canonicalizer entirely in string space until the real on-disk file
        is located.
        """
        raw_string: Optional[str] = raw_path if isinstance(raw_path, str) else None
        if raw_string is None:
            try:
                raw_string = str(raw_path)
            except (TypeError, ValueError):
                return ""
        stripped: str = raw_string.strip()
        if not stripped:
            return ""
        normalized: str = stripped.replace("\\", "/").rstrip("/")
        slash_at: int = normalized.rfind("/")
        if slash_at == -1:
            return normalized
        if slash_at == len(normalized) - 1:
            return ""
        return normalized[slash_at + 1 :]

    @staticmethod
    def _detect_repeated_prefix_drift(raw_path: str) -> Optional[str]:
        """When a descriptor path was poisoned by the previous ``os.path.relpath``
        concatenation bug the same directory prefix repeats many times before
        the *real* suffix starts (e.g. ``DEV/DXF/DEV/DXF/…/actual/parts.json``).
        Try to detect the shortest repeating leading segment and strip all
        occurrences so we can guess the true in-container relative suffix.
        """
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        normalized: str = raw_path.strip().replace("\\", "/").strip("/")
        if not normalized:
            return None
        segments: List[str] = [seg for seg in normalized.split("/") if seg]
        total: int = len(segments)
        if total < 4:
            return None

        prefix_len: int
        for prefix_len in range(1, (total // 2) + 1):
            if total % prefix_len != 0:
                continue
            pattern: Tuple[str, ...] = tuple(segments[:prefix_len])
            repeats: int = total // prefix_len
            if tuple(segments) == pattern * repeats:
                return "/".join(segments[:prefix_len])
        return None

    @staticmethod
    def _locate_unique_file_by_name(
        container_path: Path,
        file_name: str,
    ) -> Optional[Path]:
        if not file_name or not container_path.is_dir():
            return None
        matches: List[Path] = sorted(
            p for p in container_path.rglob(file_name) if p.is_file()
        )
        if len(matches) == 1:
            return matches[0]
        return None

    @classmethod
    def _resolve_short_relative_string(
        cls,
        *,
        short_relative_string: str,
        anchor_path: Path,
        resolved_container: Path,
    ) -> Optional[str]:
        """Safely join a *provenly-short* suffix to an anchor path and
        canonicalize it relative to the container directory.

        The caller guarantees ``len(short_relative_string)`` is below
        :attr:`_SAFE_RELATIVE_PATH_LENGTH_LIMIT` so the ``/`` join cannot
        trigger ``ENAMETOOLONG`` during construction.
        """
        if not isinstance(short_relative_string, str) or not short_relative_string.strip():
            return None
        if len(short_relative_string) > cls._SAFE_RELATIVE_PATH_LENGTH_LIMIT:
            return None
        try:
            relative_tail: Path = Path(short_relative_string)
            candidate: Path = (anchor_path / relative_tail).resolve()
        except (OSError, ValueError, RuntimeError):
            return None
        if not candidate.is_file():
            return None
        try:
            return candidate.relative_to(resolved_container).as_posix()
        except (ValueError, OSError):
            return None

    @staticmethod
    def _canonicalize_relative_path(
        raw_relative_path: str,
        *,
        container_path: Path,
        anchor_path: Optional[Path] = None,
    ) -> Optional[str]:
        """Convert a possibly corrupted resource path into a canonical POSIX
        relative path rooted at *container_path*.

        The strategy avoids any ``pathlib`` construction or directory join
        with the raw input string, because corrupt ``datapackage.json``
        entries produced by earlier synchronizers could exceed the OS
        ``MAXPATH`` limit and raise ``ENAMETOOLONG`` directly from the
        ``Path`` constructor or the ``/`` operator.  Canonicalization
        therefore proceeds entirely in string space until the real on-disk
        file has been identified by its trailing name (and only then uses
        ``Path.relative_to`` on the *actual* resolved filesystem path).
        """
        if not isinstance(raw_relative_path, str) or not raw_relative_path.strip():
            return None

        resolved_container: Path = container_path.expanduser().resolve()
        if not resolved_container.is_dir():
            return None

        parsed = urlparse(raw_relative_path)
        if parsed.scheme and parsed.scheme.lower() != "file":
            return None
        path_value: str = raw_relative_path
        if parsed.scheme.lower() == "file":
            path_value = url2pathname(unquote(parsed.path))

        file_name: str = ContainerDataPackageSynchronizer._basename_from_any_path(
            path_value
        )
        if not file_name:
            return None

        direct_anchor: Path = (
            anchor_path.expanduser().resolve()
            if anchor_path is not None
            else resolved_container
        )

        # --- Stage 1: join ONLY the trailing file_name (always short, no
        # risk of ENAMETOOLONG) directly to the anchor and the container root.
        try:
            direct_target: Path = (direct_anchor / file_name).resolve()
        except (OSError, ValueError, RuntimeError):
            direct_target = None
        if direct_target is not None and direct_target.is_file():
            try:
                return direct_target.relative_to(resolved_container).as_posix()
            except (OSError, ValueError):
                pass
        try:
            container_direct: Path = (resolved_container / file_name).resolve()
        except (OSError, ValueError, RuntimeError):
            container_direct = None
        if container_direct is not None and container_direct.is_file():
            try:
                return container_direct.relative_to(resolved_container).as_posix()
            except (OSError, ValueError):
                pass

        drift_prefix: Optional[str] = (
            ContainerDataPackageSynchronizer._detect_repeated_prefix_drift(
                path_value
            )
        )
        suffix_hint: str = path_value
        if drift_prefix:
            normalized_suffix: str = path_value.strip().replace("\\", "/").strip("/")
            suffix_segments: List[str] = [
                seg for seg in normalized_suffix.split("/") if seg
            ][len(drift_prefix.split("/")) :]
            suffix_hint = "/".join(suffix_segments) if suffix_segments else file_name
        suffix_basename: str = (
            ContainerDataPackageSynchronizer._basename_from_any_path(suffix_hint)
            or file_name
        )

        # --- Stage 2: try to join anchor + (suffix_hint tail or drift
        # suffix).  ONLY DO SO when the relative string is proven short
        # (below the safe length limit).  Otherwise skip straight to rglob.
        limit: int = ContainerDataPackageSynchronizer._SAFE_RELATIVE_PATH_LENGTH_LIMIT
        if suffix_hint and suffix_hint != path_value and "/" in suffix_hint:
            if len(suffix_hint) <= limit:
                result: Optional[str] = (
                    ContainerDataPackageSynchronizer._resolve_short_relative_string(
                        short_relative_string=suffix_hint,
                        anchor_path=direct_anchor,
                        resolved_container=resolved_container,
                    )
                )
                if result is not None:
                    return result
                result = ContainerDataPackageSynchronizer._resolve_short_relative_string(
                    short_relative_string=suffix_hint,
                    anchor_path=resolved_container,
                    resolved_container=resolved_container,
                )
                if result is not None:
                    return result

        # --- Stage 3: Locate by plain trailing name.  If suffix basename
        # found nothing fall back to the original (non-drift) file_name.
        located: Optional[Path] = (
            ContainerDataPackageSynchronizer._locate_unique_file_by_name(
                resolved_container,
                suffix_basename,
            )
        )
        if located is None and suffix_basename != file_name:
            located = ContainerDataPackageSynchronizer._locate_unique_file_by_name(
                resolved_container,
                file_name,
            )
        # --- Stage 4 (last resort): the poisoned path for a dataset
        # linkset/datapackage.json commonly has a real, on-disk
        # linkset/datapackage.json somewhere in the container.  Search for
        # the exact shape ``<something>/linkset/datapackage.json`` explicitly.
        if located is None and file_name == "datapackage.json":
            hint_segments: List[str] = [
                seg
                for seg in (suffix_hint or path_value).strip().replace("\\", "/").split("/")
                if seg
            ]
            try:
                linkset_idx: int = hint_segments.index("linkset")
            except ValueError:
                linkset_idx = -1
            if linkset_idx >= 0:
                tail_from_linkset: List[str] = hint_segments[linkset_idx:]
                if tail_from_linkset:
                    linkset_tail: str = "/".join(tail_from_linkset)
                    if len(linkset_tail) <= limit:
                        result = ContainerDataPackageSynchronizer._resolve_short_relative_string(
                            short_relative_string=linkset_tail,
                            anchor_path=resolved_container,
                            resolved_container=resolved_container,
                        )
                        if result is not None:
                            return result
        if located is None:
            return None
        try:
            return located.resolve().relative_to(resolved_container).as_posix()
        except (OSError, ValueError):
            return None

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
        parsed = urlparse(normalized_path)

        if parsed.scheme and parsed.scheme.lower() != "file":
            return None

        if parsed.scheme.lower() == "file":
            try:
                decoded: str = url2pathname(unquote(parsed.path))
                file_scheme_path: Path = Path(decoded).expanduser().resolve()
                try:
                    return file_scheme_path.relative_to(container_path).as_posix()
                except ValueError:
                    return None
            except (OSError, ValueError, RuntimeError):
                return None

        leading: str = normalized_path.lstrip()
        is_absolute: bool = False
        if leading:
            first_char: str = leading[0]
            if first_char in ("/", "\\"):
                is_absolute = True
            elif len(leading) >= 2 and leading[1] == ":" and first_char.isalpha():
                is_absolute = True

        candidate_path: Path
        if is_absolute:
            try:
                candidate_path = Path(normalized_path).expanduser().resolve()
            except (OSError, ValueError, RuntimeError):
                return None
        else:
            canonical_relative: Optional[str] = self._canonicalize_relative_path(
                normalized_path,
                container_path=container_path,
                anchor_path=datapackage_path.parent,
            )
            if canonical_relative is None:
                return None
            resolved_container: Path = container_path.expanduser().resolve()
            try:
                candidate_path = (
                    resolved_container / Path(canonical_relative)
                ).resolve()
            except (OSError, ValueError, RuntimeError):
                return None

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
        resolved_container: Path = container_path.expanduser().resolve()
        canonical_relative: Optional[str] = None
        if (
            isinstance(relative_path, str)
            and relative_path.strip()
            and len(relative_path) <= self._SAFE_RELATIVE_PATH_LENGTH_LIMIT
        ):
            try:
                raw_candidate: Path = (
                    resolved_container / Path(relative_path.strip())
                )
            except (OSError, ValueError, RuntimeError):
                raw_candidate = None
            if raw_candidate is not None:
                try:
                    if raw_candidate.is_file():
                        canonical_relative = (
                            raw_candidate.resolve()
                            .relative_to(resolved_container)
                            .as_posix()
                        )
                except (OSError, ValueError, RuntimeError):
                    canonical_relative = None

        if canonical_relative is None:
            canonical_relative = self._canonicalize_relative_path(
                relative_path,
                container_path=container_path,
                anchor_path=container_path,
            )
        if canonical_relative is None:
            raise ValueError(
                "Cannot build a local descriptor for a resource path that "
                f"does not resolve inside the container: {relative_path!r}"
            )
        file_path: Path = (resolved_container / Path(canonical_relative)).resolve()
        descriptor: Dict[str, Any] = dict(existing_descriptor or {})
        datapackage_dir: Path = datapackage_path.parent.expanduser().resolve()
        try:
            descriptor_relpath_raw: str = os.path.relpath(
                str(file_path),
                str(datapackage_dir),
            )
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Resource file {file_path} could not be located relative "
                f"to the datapackage directory {datapackage_dir}."
            ) from exc
        descriptor_path: str = Path(descriptor_relpath_raw).as_posix()
        if not descriptor_path or descriptor_path == ".":
            raise ValueError(
                f"Resource file {file_path} produced an empty relative "
                f"path against datapackage directory {datapackage_dir}."
            )

        inherited_name: Any = descriptor.get("name")
        sanitize_inherited: bool = False
        if isinstance(inherited_name, str):
            if len(inherited_name) > 200:
                sanitize_inherited = True
            else:
                normalized_inherited: str = inherited_name.strip()
                if not normalized_inherited:
                    sanitize_inherited = True
        else:
            sanitize_inherited = True
        if sanitize_inherited:
            descriptor["name"] = self._resource_name(canonical_relative)
        else:
            descriptor["name"] = str(inherited_name).strip()
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
