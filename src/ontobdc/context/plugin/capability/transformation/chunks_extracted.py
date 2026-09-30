from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import (
    FileMeaningSuggestionProcessState,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.etl import (
    EtlDirectoryContract,
    EtlEventContextKeys,
    EtlEventPayloadKeys,
)
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate import ContainerRoCrate

ETL_MODULE_NAME: str = "context"
ETL_PHASE_NAME: str = "suggestion"
ETL_ENTITY_NAME: str = "file"


class ChunkCandidateContract:
    """Validates the persisted contract consumed by chunk extraction."""

    LEMMA_KEY: ClassVar[str] = "lemma"
    TOKENS_KEY: ClassVar[str] = "tokens"
    LENGTH_KEY: ClassVar[str] = "length"
    COUNT_KEY: ClassVar[str] = "count"
    LANGUAGE_KEY: ClassVar[str] = "language"
    OCCURRENCES_KEY: ClassVar[str] = "occurrences"
    FILE_FREQUENCY_KEY: ClassVar[str] = "file_frequency"
    PATH_FREQUENCY_KEY: ClassVar[str] = "path_frequency"

    @classmethod
    def validate(cls, candidate: Dict[str, Any]) -> None:
        lemma: Any = candidate.get(cls.LEMMA_KEY)
        if not isinstance(lemma, str) or not lemma.strip():
            raise ValueError(
                "ChunksExtractedCapability requires every candidate to "
                "contain a non-empty lemma."
            )

        language: Any = candidate.get(cls.LANGUAGE_KEY)
        if not isinstance(language, str) or not language.strip():
            raise ValueError(
                "ChunksExtractedCapability requires every candidate to "
                "contain an identified language."
            )

        tokens: Any = candidate.get(cls.TOKENS_KEY)
        if not isinstance(tokens, list) or not tokens:
            raise ValueError(
                "ChunksExtractedCapability requires every candidate to "
                "contain a non-empty token list."
            )

        token: Any
        for token in tokens:
            if not isinstance(token, str) or not token.strip():
                raise ValueError(
                    "ChunksExtractedCapability received an invalid token "
                    f"for candidate '{lemma}'."
                )

        length: Any = candidate.get(cls.LENGTH_KEY)
        if not isinstance(length, int) or isinstance(length, bool):
            raise ValueError(
                "ChunksExtractedCapability requires candidate length to be "
                "an integer."
            )
        if length != len(tokens) or length < 2:
            raise ValueError(
                "ChunksExtractedCapability requires candidate length to "
                "match its token list and contain at least two tokens."
            )

        count: int = cls._positive_integer(candidate, cls.COUNT_KEY, lemma)
        file_frequency: int = cls._positive_integer(
            candidate,
            cls.FILE_FREQUENCY_KEY,
            lemma,
        )
        path_frequency: int = cls._positive_integer(
            candidate,
            cls.PATH_FREQUENCY_KEY,
            lemma,
        )
        if count < file_frequency or file_frequency < path_frequency:
            raise ValueError(
                "ChunksExtractedCapability received inconsistent frequency "
                f"evidence for candidate '{lemma}'."
            )

        occurrences: Any = candidate.get(cls.OCCURRENCES_KEY)
        if not isinstance(occurrences, list) or not occurrences:
            raise ValueError(
                "ChunksExtractedCapability requires every candidate to "
                "retain at least one traceable occurrence."
            )

        occurrence: Any
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                raise ValueError(
                    "ChunksExtractedCapability requires candidate occurrences "
                    "to be objects."
                )

    @staticmethod
    def _positive_integer(
        candidate: Dict[str, Any],
        key: str,
        lemma: str,
    ) -> int:
        value: Any = candidate.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(
                "ChunksExtractedCapability requires a positive integer "
                f"'{key}' for candidate '{lemma}'."
            )

        return value


class ChunkExtractionPolicy:
    """Deterministic statistical policy used to promote candidates."""

    VERSION: ClassVar[str] = "frequency-threshold-1.0.0"
    MIN_OCCURRENCE_COUNT: ClassVar[int] = 2
    MIN_FILE_FREQUENCY: ClassVar[int] = 2
    MIN_PATH_FREQUENCY: ClassVar[int] = 1

    @classmethod
    def accepts(cls, candidate: Dict[str, Any]) -> bool:
        count: Any = candidate.get(ChunkCandidateContract.COUNT_KEY)
        file_frequency: Any = candidate.get(
            ChunkCandidateContract.FILE_FREQUENCY_KEY
        )
        path_frequency: Any = candidate.get(
            ChunkCandidateContract.PATH_FREQUENCY_KEY
        )

        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError("Candidate count must be an integer.")
        if not isinstance(file_frequency, int) or isinstance(file_frequency, bool):
            raise ValueError("Candidate file_frequency must be an integer.")
        if not isinstance(path_frequency, int) or isinstance(path_frequency, bool):
            raise ValueError("Candidate path_frequency must be an integer.")

        return (
            count >= cls.MIN_OCCURRENCE_COUNT
            and file_frequency >= cls.MIN_FILE_FREQUENCY
            and path_frequency >= cls.MIN_PATH_FREQUENCY
        )

    @classmethod
    def configuration(cls) -> Dict[str, Any]:
        return {
            "policy_version": cls.VERSION,
            "min_occurrence_count": cls.MIN_OCCURRENCE_COUNT,
            "min_file_frequency": cls.MIN_FILE_FREQUENCY,
            "min_path_frequency": cls.MIN_PATH_FREQUENCY,
        }

    @staticmethod
    def sort_key(candidate: Dict[str, Any]) -> Tuple[int, int, int, int, str, str]:
        path_frequency: Any = candidate.get(
            ChunkCandidateContract.PATH_FREQUENCY_KEY
        )
        file_frequency: Any = candidate.get(
            ChunkCandidateContract.FILE_FREQUENCY_KEY
        )
        count: Any = candidate.get(ChunkCandidateContract.COUNT_KEY)
        length: Any = candidate.get(ChunkCandidateContract.LENGTH_KEY)
        language: Any = candidate.get(ChunkCandidateContract.LANGUAGE_KEY)
        lemma: Any = candidate.get(ChunkCandidateContract.LEMMA_KEY)

        if not isinstance(path_frequency, int):
            raise ValueError("Candidate path_frequency must be an integer.")
        if not isinstance(file_frequency, int):
            raise ValueError("Candidate file_frequency must be an integer.")
        if not isinstance(count, int):
            raise ValueError("Candidate count must be an integer.")
        if not isinstance(length, int):
            raise ValueError("Candidate length must be an integer.")
        if not isinstance(language, str):
            raise ValueError("Candidate language must be a string.")
        if not isinstance(lemma, str):
            raise ValueError("Candidate lemma must be a string.")

        return (
            -path_frequency,
            -file_frequency,
            -count,
            -length,
            language,
            lemma,
        )


class ChunkIdentity:
    """Builds a stable identifier inside one language-specific semantic scope."""

    @staticmethod
    def of(language: str, lemma: str) -> str:
        canonical_key: str = f"{language.strip().lower()}\x00{lemma.strip().lower()}"
        digest: str = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()
        return f"chunk-{digest}"


class ChunksExtractedCapability(TransactionCapability):
    """
    Promotes statistically supported chunk candidates to accepted chunks.

    This capability is deliberately pre-semantic: it uses only persisted,
    explainable corpus evidence. It does not call an embedding model, an
    ontology, a reasoner, or an LLM.
    """

    CANDIDATES_KEY: ClassVar[str] = "chunk_candidates"
    ITEMS_KEY: ClassVar[str] = "items"
    CHUNKS_KEY: ClassVar[str] = "chunks"
    CHUNK_ID_KEY: ClassVar[str] = "chunk_id"
    STATE_NAME: ClassVar[str] = "chunks_extracted"
    SOURCE_STATE_NAME: ClassVar[str] = "chunk_candidates_generated"
    EXTRACTION_VERSION_KEY: ClassVar[str] = "chunk-extraction-version"
    EXTRACTION_VERSION: ClassVar[str] = "1.0.0"
    CANDIDATE_VERSION_KEY: ClassVar[str] = "chunk-candidate-generation-version"
    # SOURCE_EVENT_FILE_NAME: ClassVar[str] = f"{SOURCE_STATE_NAME}.json"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.CHUNKS_EXTRACTED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "chunks_extracted"
        ),
        version="1.0.0",
        name="Chunks Extracted",
        description=(
            "Promote statistically supported chunk candidates to accepted "
            "chunks and persist the deterministic result as an ETL event."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["suggestion", "file", "chunk", "statistics", "etl"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                EtlEventContextKeys.CONTAINER_PATH: {
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
                "chunk_count": {
                    "type": "integer",
                },
                CHUNKS_KEY: {
                    "type": "object",
                },
            },
        },
        log_message={
            "info": {
                "en": "Statistically supported chunk candidates were extracted.",
            },
            "debug_entry": {
                "en": "Extracting supported chunks from persisted candidates.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return "Chunks Extracted"
        if normalized_language == "pt-br":
            return "Chunks Extraídos"

        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def description(self, lang: str = "en") -> str:
        normalized_language: str = lang.strip().lower().replace("_", "-")
        if normalized_language == "en":
            return (
                "Statistically supported chunk candidates have been promoted "
                "to deterministic accepted chunks."
            )
        if normalized_language == "pt-br":
            return (
                "Os candidatos a chunk com suporte estatístico foram "
                "promovidos a chunks aceitos de forma determinística."
            )

        raise ValueError(f"Unsupported presentation language: '{lang}'.")

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context,
            EtlEventContextKeys.CONTAINER_PATH,
        )
        if container_path_value is None:
            return False

        container_path: Path = Path(container_path_value).expanduser().resolve()
        event_path: Path = ChunksExtractedCapability.event_path(container_path)
        if not event_path.is_file():
            return False

        event: Dict[str, Any] = json.loads(
            event_path.read_text(encoding="utf-8")
        )
        recorded_hash: Any = event.get(EtlEventPayloadKeys.RO_CRATE_HASH)
        if not isinstance(recorded_hash, str) or not recorded_hash.strip():
            return False
        if recorded_hash != ContainerRoCrate.file_hash(container_path):
            return False

        extraction_version: Any = event.get(self.EXTRACTION_VERSION_KEY)
        if extraction_version != self.EXTRACTION_VERSION:
            return False

        chunks: Any = event.get(self.CHUNKS_KEY)
        if not isinstance(chunks, dict):
            return False
        configuration: Any = chunks.get("configuration")
        if not isinstance(configuration, dict):
            return False
        policy_version: Any = configuration.get("policy_version")
        if policy_version != ChunkExtractionPolicy.VERSION:
            return False
        items: Any = chunks.get(self.ITEMS_KEY)
        if not isinstance(items, list):
            return False

        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, EtlEventContextKeys.CONTAINER_PATH)
        ).expanduser().resolve()

        candidate_event_content: str = StateWorkerAdapter.get_persisted_event(
            ChunksExtractedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED
        )
        candidate_event: Dict[str, Any] = json.loads(candidate_event_content)
        # self._validate_candidate_event(container_path, candidate_event)

        chunk_candidates_raw: Any = candidate_event[self.CANDIDATES_KEY]
        if not isinstance(chunk_candidates_raw, dict):
            raise ValueError(
                "ChunksExtractedCapability requires a chunk_candidates object."
            )
        chunk_candidates: Dict[str, Any] = chunk_candidates_raw

        candidate_items_raw: Any = chunk_candidates[self.ITEMS_KEY]
        if not isinstance(candidate_items_raw, list):
            raise ValueError(
                "ChunksExtractedCapability requires chunk_candidates.items "
                "to be a list."
            )
        candidate_items: List[Any] = candidate_items_raw

        chunks: List[Dict[str, Any]] = self._extract(candidate_items)
        candidate_generation_version: Any = candidate_event.get(
            self.CANDIDATE_VERSION_KEY
        )
        if not isinstance(candidate_generation_version, str):
            candidate_generation_version = ""
        event: Dict[str, Any] = {
            "state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            EtlEventPayloadKeys.RO_CRATE_HASH: ContainerRoCrate.file_hash(container_path),
            self.CANDIDATE_VERSION_KEY: candidate_generation_version,
            self.EXTRACTION_VERSION_KEY: self.EXTRACTION_VERSION,
            self.CHUNKS_KEY: {
                "configuration": ChunkExtractionPolicy.configuration(),
                self.ITEMS_KEY: chunks,
            },
            "chunk_count": len(chunks),
        }
        event_path: Path = self._write_event(container_path, event)

        return {
            "resulting_state": self.STATE_NAME,
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
        }

    @classmethod
    def _extract(cls, candidate_items: List[Any]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        chunk_ids: Dict[str, str] = {}
        candidate: Any
        for candidate in candidate_items:
            if not isinstance(candidate, dict):
                raise ValueError(
                    "ChunksExtractedCapability requires every candidate item "
                    "to be an object."
                )

            typed_candidate: Dict[str, Any] = candidate
            ChunkCandidateContract.validate(typed_candidate)
            if not ChunkExtractionPolicy.accepts(typed_candidate):
                continue

            language_value: Any = typed_candidate.get(
                ChunkCandidateContract.LANGUAGE_KEY
            )
            lemma_value: Any = typed_candidate.get(
                ChunkCandidateContract.LEMMA_KEY
            )
            if not isinstance(language_value, str):
                raise ValueError("Candidate language must be a string.")
            if not isinstance(lemma_value, str):
                raise ValueError("Candidate lemma must be a string.")

            chunk_id: str = ChunkIdentity.of(language_value, lemma_value)
            if chunk_id in chunk_ids:
                previous_lemma: str = chunk_ids[chunk_id]
                raise ValueError(
                    "ChunksExtractedCapability received duplicate canonical "
                    f"candidate '{previous_lemma}'."
                )
            chunk_ids[chunk_id] = lemma_value

            chunk: Dict[str, Any] = dict(typed_candidate)
            chunk[cls.CHUNK_ID_KEY] = chunk_id
            chunks.append(chunk)

        chunks.sort(key=ChunkExtractionPolicy.sort_key)
        return chunks

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
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
