from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.shared.adapter.worker import StateWorkerAdapter
import stanza
from stanza.pipeline.core import Pipeline
from stanza.models.common.doc import Document

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import FileMeaningSuggestionProcessState

from ontobdc.storage.plugin.capability.transformation import (
    CONTAINER_PATH_KEY,
    ETL_DIRECTORY_NAME,
    ETL_ENTITY_NAME,
    ETL_MODULE_NAME,
    ETL_PHASE_NAME,
    LANGUAGE_CODES,
    LANGUAGE_RESULT_KEY,
    NORMALIZED_PATH_RESULT_KEY,
    RO_CRATE_HASH_KEY,
)


class PathLanguageIdentifiedCapability(TransactionCapability):
    """Identify the language of every normalized path."""

    IDENTIFICATION_VERSION_KEY: ClassVar[str] = "language-identification-version"
    IDENTIFICATION_VERSION: ClassVar[str] = "stanza-1.0.0"
    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id="org.ontobdc.suggest.plugin.capability.transformation.target.path_language_identified",
        version="1.0.0",
        name="Path Language Identified",
        description=(
            "Identify the language of every normalized file path and "
            "persist the result as an ETL event file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["suggestion", "file", "path", "language", "etl"],
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
                "en": "The language of every normalized file path was identified.",
            },
            "debug_entry": {
                "en": "Identifying the language of every normalized file path.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED.label(lang)

    def description(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED.description(
            lang
        )

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context, CONTAINER_PATH_KEY
        )
        if container_path_value is None:
            return False

        container_path: Path = Path(container_path_value).expanduser().resolve()
        if not self.event_path(container_path).is_file():
            return False

        event_content: str = StateWorkerAdapter.get_persisted_event(
            self.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED
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
        normalized_event_path: Path = (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / ETL_DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / f"{FileMeaningSuggestionProcessState.PATH_NORMALIZED.value}.json"
        )
        if not normalized_event_path.is_file():
            raise ValueError(
                "PathLanguageIdentifiedCapability requires the persisted "
                "path-normalized event to be present."
            )
        normalized_event: Dict[str, Any] = json.loads(
            normalized_event_path.read_text(encoding="utf-8")
        )
        normalized_files_raw: Any = normalized_event["files"]
        if not isinstance(normalized_files_raw, list):
            raise ValueError(
                "PathLanguageIdentifiedCapability requires a path-normalized "
                "event containing a file list."
            )
        normalized_files: List[Any] = normalized_files_raw

        file_entry: Any
        for file_entry in normalized_files:
            if not isinstance(file_entry, dict):
                raise ValueError(
                    "PathLanguageIdentifiedCapability received a non-object "
                    "entry in the path-normalized file list."
                )
            normalized_path_raw: Any = file_entry[NORMALIZED_PATH_RESULT_KEY]
            if (
                not isinstance(normalized_path_raw, str)
                or not normalized_path_raw.strip()
            ):
                raise ValueError(
                    "PathLanguageIdentifiedCapability requires every file "
                    "entry to contain a non-empty normalized_path."
                )

            detected_language: str = self._identify_language(
                normalized_path_raw
            )
            file_entry[LANGUAGE_RESULT_KEY] = detected_language

        event: Dict[str, Any] = {
            **normalized_event,
            "state": FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED.value.strip(
                "_"
            ),
            self.IDENTIFICATION_VERSION_KEY: self.IDENTIFICATION_VERSION,
        }
        event_path: Path = self._write_event(container_path, event)

        return {
            "resulting_state": FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED,
            CONTAINER_PATH_KEY: str(container_path),
            "event_path": str(event_path),
        }

    @classmethod
    def _identify_language(cls, normalized_path: str) -> str:
        document: Document = cls._detector()(normalized_path)
        detected_language: Optional[str] = document.lang
        if detected_language not in LANGUAGE_CODES:
            raise ValueError(
                "Could not identify the language of normalized path "
                f"'{normalized_path}'."
            )

        return LANGUAGE_CODES[detected_language]

    @classmethod
    @lru_cache(maxsize=1)
    def _detector(cls) -> Pipeline:
        language_identifiers: List[str] = list(LANGUAGE_CODES)
        return stanza.Pipeline(
            lang="multilingual",
            processors="langid",
            langid_lang_subset=language_identifiers,
            verbose=False,
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
    def _write_event(cls, container_path: Path, event: Dict[str, Any]) -> Path:
        event_path: Path = cls.event_path(container_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

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
