from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache
from typing import Any, ClassVar, Dict, List, Optional

import stanza
from stanza.pipeline.core import Pipeline
from stanza.models.common.doc import Document, Sentence, Word

from ontobdc.shared.adapter.worker import StateWorkerAdapter
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
    LEMMA_RESULT_KEY,
    NORMALIZED_PATH_RESULT_KEY,
    RO_CRATE_HASH_KEY,
)


class PathLemmatizedCapability(TransactionCapability):
    """
    Reduces every normalized path to its lemma, and persists the result
    as an ETL event file.

    Lemmatization runs on the language-specific Stanza pipeline so part-of-
    speech and morphological context inform each lemma.
    """
    LEMMATIZATION_VERSION_KEY: ClassVar[str] = "lemmatization-version"
    LEMMATIZATION_VERSION: ClassVar[str] = "stanza-1.0.0"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.PATH_LEMMATIZED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id="org.ontobdc.suggest.plugin.capability.transformation.target.path_lemmatized",
        version="1.0.0",
        name="Path Lemmatized",
        description=(
            "Reduce every file path the RO-Crate states, once normalized, "
            "to its lemma, and persist the result as an ETL event file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["suggestion", "file", "path", "lemma", "stanza", "etl"],
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
                    "Every normalized file path was reduced to its lemma."
                ),
            },
            "debug_entry": {
                "en": "Reducing every normalized file path to its lemma.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_LEMMATIZED.label(lang)

    def description(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_LEMMATIZED.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context, CONTAINER_PATH_KEY
        )
        if container_path_value is None:
            return False

        container_path: Path = Path(container_path_value).expanduser().resolve()
        if not PathLemmatizedCapability.event_path(container_path).is_file():
            return False

        event_content: str = StateWorkerAdapter.get_persisted_event(
            PathLemmatizedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.PATH_LEMMATIZED
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

        language_event_path: Path = (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / ETL_DIRECTORY_NAME
            / ETL_MODULE_NAME
            / ETL_PHASE_NAME
            / ETL_ENTITY_NAME
            / f"{FileMeaningSuggestionProcessState.PATH_LANGUAGE_IDENTIFIED.value}.json"
        )
        if not language_event_path.is_file():
            raise ValueError(
                "PathLemmatizedCapability requires the persisted "
                "path-language-identified event to be present."
            )
        language_event: Dict[str, Any] = json.loads(
            language_event_path.read_text(encoding="utf-8")
        )

        event: Dict[str, Any] = {
            **language_event,
            "state": FileMeaningSuggestionProcessState.PATH_LEMMATIZED.value.strip(
                "_"
            ),
            self.LEMMATIZATION_VERSION_KEY: self.LEMMATIZATION_VERSION,
        }

        identified_files_raw: Any = language_event["files"]
        if not isinstance(identified_files_raw, list):
            raise ValueError(
                "PathLemmatizedCapability requires a path-language-identified "
                "event containing a file list."
            )
        identified_files: List[Any] = identified_files_raw
        lemmatized_files: List[Dict[str, Any]] = []

        file_entry: Any
        for file_entry in identified_files:
            if not isinstance(file_entry, dict):
                raise ValueError(
                    "PathLemmatizedCapability received a non-object entry "
                    "in the path-language-identified file list."
                )
            normalized_path_raw: Any = file_entry[NORMALIZED_PATH_RESULT_KEY]
            language_raw: Any = file_entry[LANGUAGE_RESULT_KEY]

            if (
                not isinstance(normalized_path_raw, str)
                or not normalized_path_raw.strip()
            ):
                raise ValueError(
                    "PathLemmatizedCapability requires every file entry to "
                    "contain a non-empty normalized_path."
                )
            if not isinstance(language_raw, str) or not language_raw.strip():
                raise ValueError(
                    "PathLemmatizedCapability requires every file entry to "
                    "contain an identified language."
                )
            if language_raw not in LANGUAGE_CODES.values():
                raise ValueError(
                    "PathLemmatizedCapability received unsupported language "
                    f"'{language_raw}'."
                )

            working_entry: Dict[str, Any] = dict(file_entry)
            working_entry[LEMMA_RESULT_KEY] = self._lemmatize(
                normalized_path_raw,
                language_raw,
            )
            lemmatized_files.append(working_entry)

        event["files"] = lemmatized_files
        event_path: Path = self._write_event(container_path, event)

        return {
            "resulting_state": FileMeaningSuggestionProcessState.PATH_LEMMATIZED,
            CONTAINER_PATH_KEY: str(container_path),
            "event_path": str(event_path),
        }

    @classmethod
    def _lemmatize(cls, value: str, language: str) -> str:
        """
        Return the lemma of the given normalized text using a contextual,
        language-specific Stanza pipeline.
        """
        pipeline: Pipeline = cls._language_pipeline(language)
        document: Document = pipeline(value)
        lemmas: List[str] = []
        sentence: Sentence
        for sentence in document.sentences:
            word: Word
            for word in sentence.words:
                if word.upos == "PUNCT":
                    continue
                lemma: Optional[str] = word.lemma
                if not isinstance(lemma, str) or not lemma.strip():
                    raise ValueError(
                        "Stanza returned no lemma for token "
                        f"'{word.text}' in path '{value}'."
                    )
                lemmas.append(lemma.strip().lower())

        return " ".join(lemmas)

    @classmethod
    @lru_cache(maxsize=8)
    def _language_pipeline(cls, language: str) -> Pipeline:
        normalized_language: str = language.strip().lower().split("-", 1)[0]

        return stanza.Pipeline(
            lang=normalized_language,
            processors="tokenize,mwt,pos,lemma",
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
        """
        Atomically write the ETL event file (temp file, then replace) so a
        reader never observes a partially written event.
        """
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
