from __future__ import annotations

import os
import json
from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone

from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.storage.adapter.loader import FileTypificationLoader
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StoragePathStatHelper,
)
from ontobdc.storage.adapter.file_mime import FileMimeDetector
from ontobdc.storage.adapter.typification import FileTypificationEvaluator
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.capability.transformation import (
    CONTAINER_PATH_KEY,
    RO_CRATE_HASH_KEY,
    ETL_MODULE_NAME,
    ETL_PHASE_NAME,
    ETL_ENTITY_NAME,
    ETL_DIRECTORY_NAME,
    SOURCE_PATH_RESULT_KEY,
    CONTENT_SIZE_KEY,
    DATE_MODIFIED_KEY,
    DATE_CREATED_KEY,
    METADATA_RESULT_KEY,
    MIME_RESULT_KEY,
    EVALUATION_RESULT_KEY,
)
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import FileMeaningSuggestionProcessState


class FileMetadataExtractedCapability(TransactionCapability):
    """
    Extracts standard metadata, MIME type, and a specific type for every
    file the container's RO-Crate states, and persists the result as an
    ETL event file.

    Typing a file is not this capability's own decision: it delegates to
    whichever ``FileTypificationStrategyPort`` the plugin loader discovers
    that supports the file, the same "the plugin owns the answer" design
    ``StrategyParamResolver`` already uses for resolving a capability's own
    inputs.
    """
    NAME_KEY: ClassVar[str] = "name"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id="org.ontobdc.suggest.plugin.capability.transformation.target.file_metadata_extracted",
        version="1.0.0",
        name="File Metadata Extracted",
        description=(
            "Extract standard metadata, MIME type, and a specific type for "
            "every file a container's RO-Crate states, and persist the "
            "result as an ETL event file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["suggestion", "file", "metadata", "mime", "typification", "etl"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                CONTAINER_PATH_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "properties": {
                "event_path": {
                    "type": "string",
                },
                "file_count": {
                    "type": "integer",
                },
                "files": {
                    "type": "array",
                },
            },
        },
        log_message={
            "info": {
                "en": (
                    "Every file the RO-Crate states had its metadata, MIME "
                    "type, and specific type extracted."
                ),
            },
            "debug_entry": {
                "en": (
                    "Extracting metadata, MIME type, and specific type for "
                    "every file the container's RO-Crate states."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED.label(lang)

    def description(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context, CONTAINER_PATH_KEY
        )
        if container_path_value is None:
            return False

        container_path: Path = Path(container_path_value).expanduser().resolve()
        if not FileMetadataExtractedCapability.event_path(container_path).is_file():
            return False

        event_content: str = StateWorkerAdapter.get_persisted_event(
            FileMetadataExtractedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED
        )

        event_data: Dict[str, Any] = json.loads(event_content)

        if RO_CRATE_HASH_KEY not in event_data:
            return False

        if event_data[RO_CRATE_HASH_KEY] != ContainerRoCrate.file_hash(container_path):
            return False

        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, CONTAINER_PATH_KEY)
        ).expanduser().resolve()

        evaluator: FileTypificationEvaluator = FileTypificationEvaluator(
            FileTypificationLoader()
        )
        source_paths: List[str] = ContainerRoCrate.file_paths(container_path)
        files: List[Dict[str, Any]] = []
        source_path: str
        for source_path in source_paths:
            file_metadata: Optional[Dict[str, Any]] = self._metadata_of(
                container_path / source_path
            )
            if file_metadata is None:
                continue

            mime: Optional[str]
            encoding: Optional[str]
            mime, encoding = FileMimeDetector.of(source_path)

            files.append({
                SOURCE_PATH_RESULT_KEY: source_path,
                METADATA_RESULT_KEY: file_metadata,
                MIME_RESULT_KEY: mime,
                EVALUATION_RESULT_KEY: evaluator.evaluate(source_path, mime),
            })

        event_path: Path = self._write_event(container_path, files)

        return {
            "resulting_state": FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED,
            CONTAINER_PATH_KEY: str(container_path),
            "event_path": str(event_path),
        }

    @classmethod
    def _metadata_of(cls, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Return the file's standard metadata, or ``None`` when the file has
        genuinely vanished between the RO-Crate read and this call (a
        synced folder actively propagating a delete), matching how the
        manifest-synced hotfix drops the same kind of stale entry.
        """
        stat_result: Any = StoragePathStatHelper.safe_stat(file_path)
        if stat_result is None:
            return None

        metadata: Dict[str, Any] = {
            cls.NAME_KEY: file_path.name,
            CONTENT_SIZE_KEY: str(stat_result.st_size),
            DATE_MODIFIED_KEY: cls._iso_utc(stat_result.st_mtime),
        }

        birth_time: Any = getattr(stat_result, "st_birthtime", None)
        if birth_time is None and os.name == "nt":
            birth_time = stat_result.st_ctime
        if birth_time is not None:
            metadata[DATE_CREATED_KEY] = cls._iso_utc(float(birth_time))

        return metadata

    @staticmethod
    def _iso_utc(timestamp: float) -> str:
        return (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / ETL_DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / cls.ETL_EVENT_FILE_NAME
        )

    @classmethod
    def _write_event(
        cls,
        container_path: Path,
        files: List[Dict[str, Any]],
    ) -> Path:
        """
        Atomically write the ETL event file (temp file, then replace) so a
        reader never observes a partially written event.
        """
        event_path: Path = cls.event_path(container_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        event: Dict[str, Any] = {
            "state": FileMeaningSuggestionProcessState.FILE_METADATA_EXTRACTED.value.strip(
                "_"
            ),
            CONTAINER_PATH_KEY: str(container_path),
            RO_CRATE_HASH_KEY: ContainerRoCrate.file_hash(container_path),
            "file_count": len(files),
            "files": files,
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
