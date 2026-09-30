from __future__ import annotations

import os
import json
import stat as stat_module
from typing import Any, ClassVar, Dict, Optional
from pathlib import Path
from datetime import datetime, timezone

from ontobdc.shared.adapter.etl import (
    EtlEventPayloadKeys,
)
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.taxonomy import OpenFileMetadataTaxonomy
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StoragePathStatHelper,
)
from ontobdc.storage.adapter.file_mime import FileMimeDetector
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.open_file_metadata import OpenFileMetadataEvent
from ontobdc.storage.plugin.machine.open_file.port import OpenFileChainSupport


class SingleFileMetadataExtractedCapability(TransactionCapability):
    """Extract cheap filesystem metadata for one file and persist an ETL event."""

    STATE_NAME: ClassVar[str] = OpenFileMetadataTaxonomy.STATE_NAME
    ETL_EVENT_FILE_NAME: ClassVar[str] = OpenFileMetadataTaxonomy.EVENT_FILE_NAME

    ETL_MODULE_NAME: ClassVar[str] = OpenFileMetadataTaxonomy.MODULE_NAME
    ETL_PHASE_NAME: ClassVar[str] = OpenFileMetadataTaxonomy.PHASE_NAME
    ETL_ENTITY_NAME: ClassVar[str] = OpenFileMetadataTaxonomy.ENTITY_NAME

    RESOLVED_PATH_KEY: ClassVar[str] = OpenFileMetadataTaxonomy.RESOLVED_PATH_KEY
    PATH_CONFIRMED_KEY: ClassVar[str] = "path_confirmed"
    NAME_KEY: ClassVar[str] = "name"
    STEM_KEY: ClassVar[str] = "stem"
    SUFFIX_KEY: ClassVar[str] = "suffix"
    MIME_ENCODING_KEY: ClassVar[str] = "mime_encoding"
    DATE_ACCESSED_KEY: ClassVar[str] = "dateAccessed"
    FILE_MODE_KEY: ClassVar[str] = "fileMode"
    PERMISSIONS_KEY: ClassVar[str] = "permissions"
    INODE_KEY: ClassVar[str] = "inode"
    LINK_COUNT_KEY: ClassVar[str] = "linkCount"
    UID_KEY: ClassVar[str] = "uid"
    GID_KEY: ClassVar[str] = "gid"
    IS_SYMLINK_KEY: ClassVar[str] = "isSymlink"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation."
            "single_file_metadata_extracted"
        ),
        version="1.0.0",
        name="Single File Metadata Extracted",
        description=(
            "Confirm one file path, extract its MIME type and cheap filesystem "
            "metadata, and persist the result as an ETL state event."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "file", "metadata", "mime", "etl", "open_file"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                OpenFileChainSupport.PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "properties": {
                "event_path": {"type": "string"},
                RESOLVED_PATH_KEY: {"type": "string"},
                EtlEventPayloadKeys.MIME: {"type": "string"},
                EtlEventPayloadKeys.METADATA: {"type": "object"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        raw_path: Optional[str] = RequiredParameter.optional(
            context,
            OpenFileChainSupport.PATH_KEY,
        )
        if raw_path is None:
            return False

        source_path = Path(raw_path).expanduser()
        resolved_path = source_path.resolve()
        stat_result: Optional[Any] = StoragePathStatHelper.safe_stat(resolved_path)
        if stat_result is None or not resolved_path.is_file():
            return False

        try:
            root_path = StorageBootstrap.get_init_root_path(context=context)
            event_path = self.event_path(root_path)
            payload = json.loads(event_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False

        if not isinstance(payload, dict) or EtlEventPayloadKeys.MIME not in payload:
            return False
        persisted_mime: Any = payload[EtlEventPayloadKeys.MIME]
        if persisted_mime is None:
            if resolved_path.suffix:
                return False
        elif not isinstance(persisted_mime, str) or not persisted_mime.strip():
            return False

        metadata: Any = payload.get(EtlEventPayloadKeys.METADATA)
        if not isinstance(metadata, dict):
            return False

        return (
            payload.get("state") == self.STATE_NAME
            and payload.get(self.RESOLVED_PATH_KEY) == str(resolved_path)
            and metadata.get(self.PATH_CONFIRMED_KEY) is True
            and metadata.get(EtlEventPayloadKeys.CONTENT_SIZE)
            == str(stat_result.st_size)
            and metadata.get(EtlEventPayloadKeys.DATE_MODIFIED)
            == self._iso_utc(stat_result.st_mtime)
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        raw_path: str = RequiredParameter.of(context, OpenFileChainSupport.PATH_KEY)
        source_path: Path = Path(raw_path).expanduser()
        resolved_path: Path = source_path.resolve()

        stat_result: Optional[Any] = StoragePathStatHelper.safe_stat(resolved_path)
        if stat_result is None or not resolved_path.is_file():
            raise FileNotFoundError(f"File does not exist on disk: {resolved_path}")

        mime_type: Optional[str]
        mime_encoding: Optional[str]
        mime_type, mime_encoding = FileMimeDetector.of(resolved_path.name)
        metadata: Dict[str, Any] = self._metadata_of(
            source_path=source_path,
            resolved_path=resolved_path,
            stat_result=stat_result,
        )

        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        event_path: Path = self._write_event(
            root_path=root_path,
            source_path=source_path,
            resolved_path=resolved_path,
            mime_type=mime_type,
            mime_encoding=mime_encoding,
            metadata=metadata,
        )

        return {
            "resulting_state": self.STATE_NAME,
            "event_path": str(event_path),
            self.RESOLVED_PATH_KEY: str(resolved_path),
            EtlEventPayloadKeys.MIME: mime_type,
            EtlEventPayloadKeys.METADATA: metadata,
        }

    @classmethod
    def _metadata_of(
        cls,
        source_path: Path,
        resolved_path: Path,
        stat_result: Any,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            cls.PATH_CONFIRMED_KEY: True,
            cls.NAME_KEY: resolved_path.name,
            cls.STEM_KEY: resolved_path.stem,
            cls.SUFFIX_KEY: resolved_path.suffix,
            EtlEventPayloadKeys.CONTENT_SIZE: str(stat_result.st_size),
            EtlEventPayloadKeys.DATE_MODIFIED: cls._iso_utc(stat_result.st_mtime),
            cls.DATE_ACCESSED_KEY: cls._iso_utc(stat_result.st_atime),
            cls.FILE_MODE_KEY: stat_module.filemode(stat_result.st_mode),
            cls.PERMISSIONS_KEY: oct(stat_module.S_IMODE(stat_result.st_mode)),
            cls.INODE_KEY: stat_result.st_ino,
            cls.LINK_COUNT_KEY: stat_result.st_nlink,
            cls.IS_SYMLINK_KEY: source_path.is_symlink(),
        }

        uid: Any = getattr(stat_result, "st_uid", None)
        if uid is not None:
            metadata[cls.UID_KEY] = uid

        gid: Any = getattr(stat_result, "st_gid", None)
        if gid is not None:
            metadata[cls.GID_KEY] = gid

        birth_time: Any = getattr(stat_result, "st_birthtime", None)
        if birth_time is None and os.name == "nt":
            birth_time = stat_result.st_ctime
        if birth_time is not None:
            metadata[EtlEventPayloadKeys.DATE_CREATED] = cls._iso_utc(
                float(birth_time)
            )

        return metadata

    @staticmethod
    def _iso_utc(timestamp: float) -> str:
        return (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @classmethod
    def event_path(cls, root_path: Path) -> Path:
        return OpenFileMetadataEvent.path(root_path)

    @classmethod
    def _write_event(
        cls,
        root_path: Path,
        source_path: Path,
        resolved_path: Path,
        mime_type: Optional[str],
        mime_encoding: Optional[str],
        metadata: Dict[str, Any],
    ) -> Path:
        event_path: Path = cls.event_path(root_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        event: Dict[str, Any] = {
            "state": cls.STATE_NAME,
            EtlEventPayloadKeys.SOURCE_PATH: str(source_path),
            cls.RESOLVED_PATH_KEY: str(resolved_path),
            EtlEventPayloadKeys.MIME: mime_type,
            cls.MIME_ENCODING_KEY: mime_encoding,
            EtlEventPayloadKeys.METADATA: metadata,
        }

        serialized: str = json.dumps(
            event,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary_path: Path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(event_path)

        return event_path
