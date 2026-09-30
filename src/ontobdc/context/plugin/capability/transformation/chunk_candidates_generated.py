from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.tokenizer import TokenStatisticsTokenizer
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import (
    FileMeaningSuggestionProcessState,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.etl import (
    EtlDirectoryContract,
    EtlEventContextKeys,
    EtlEventPayloadKeys,
    EtlLanguageContract,
)
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate import ContainerRoCrate

ETL_MODULE_NAME: str = "context"
ETL_PHASE_NAME: str = "suggestion"
ETL_ENTITY_NAME: str = "file"


class ChunkCandidateAccumulator:
    """Aggregate every occurrence of one language-specific candidate."""

    def __init__(self, language: str, tokens: List[str]) -> None:
        self._language: str = language
        self._tokens: List[str] = list(tokens)
        self._lemma: str = " ".join(tokens)
        self._source_paths: Set[str] = set()
        self._lemma_paths: Set[str] = set()
        self._occurrences: List[Dict[str, Any]] = []
        self._left_boundaries: Dict[str, int] = {}
        self._right_boundaries: Dict[str, int] = {}

    def add_occurrence(
        self,
        source_path: str,
        lemma_path: str,
        start: int,
        end: int,
        left_boundary: str,
        right_boundary: str,
    ) -> None:
        self._source_paths.add(source_path)
        self._lemma_paths.add(lemma_path)
        self._left_boundaries[left_boundary] = (
            self._left_boundaries.get(left_boundary, 0) + 1
        )
        self._right_boundaries[right_boundary] = (
            self._right_boundaries.get(right_boundary, 0) + 1
        )
        self._occurrences.append(
            {
                "source_id": source_path,
                "source_path": source_path,
                "lemma_path": lemma_path,
                "language": self._language,
                "start": start,
                "end": end,
            }
        )

    def payload(self) -> Dict[str, Any]:
        occurrences: List[Dict[str, Any]] = sorted(
            self._occurrences,
            key=lambda occurrence: (
                occurrence["source_path"],
                occurrence["lemma_path"],
                occurrence["start"],
                occurrence["end"],
            ),
        )
        return {
            "lemma": self._lemma,
            "tokens": list(self._tokens),
            "length": len(self._tokens),
            "language": self._language,
            "count": len(occurrences),
            "file_frequency": len(self._source_paths),
            "path_frequency": len(self._lemma_paths),
            "left_boundaries": dict(sorted(self._left_boundaries.items())),
            "right_boundaries": dict(sorted(self._right_boundaries.items())),
            "occurrences": occurrences,
        }


class ChunkCandidateGenerator:
    """Enumerate and aggregate all observed contiguous multi-token windows."""

    MINIMUM_LENGTH: ClassVar[int] = 2

    @classmethod
    def generate(
        cls,
        source_records: List[Any],
        token_statistics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        token_entries: Any = token_statistics.get("tokens")
        if not isinstance(token_entries, dict):
            raise ValueError(
                "ChunkCandidatesGeneratedCapability requires token statistics "
                "containing a tokens object."
            )

        records: List[Tuple[str, str, str]] = cls._records(source_records)
        accumulators: Dict[
            Tuple[str, str], ChunkCandidateAccumulator
        ] = {}
        source_path: str
        language: str
        lemma_path: str
        for source_path, language, lemma_path in records:
            ordered_tokens: List[str]
            ordered_tokens, _ = TokenStatisticsTokenizer.tokenize(lemma_path)
            tokens: List[str] = ordered_tokens[1:-1]
            cls._validate_tokens(tokens, token_entries, source_path)

            length: int
            for length in range(cls.MINIMUM_LENGTH, len(tokens) + 1):
                start: int
                for start in range(0, len(tokens) - length + 1):
                    end: int = start + length
                    candidate_tokens: List[str] = tokens[start:end]
                    candidate_lemma: str = " ".join(candidate_tokens)
                    key: Tuple[str, str] = (language, candidate_lemma)
                    if key not in accumulators:
                        accumulators[key] = ChunkCandidateAccumulator(
                            language,
                            candidate_tokens,
                        )

                    left_boundary: str = (
                        TokenStatisticsTokenizer.BOS
                        if start == 0
                        else tokens[start - 1]
                    )
                    right_boundary: str = (
                        TokenStatisticsTokenizer.EOS
                        if end == len(tokens)
                        else tokens[end]
                    )
                    accumulators[key].add_occurrence(
                        source_path=source_path,
                        lemma_path=lemma_path,
                        start=start,
                        end=end,
                        left_boundary=left_boundary,
                        right_boundary=right_boundary,
                    )

        candidates: List[Dict[str, Any]] = [
            accumulator.payload() for accumulator in accumulators.values()
        ]
        candidates.sort(
            key=lambda candidate: (
                candidate["language"],
                candidate["lemma"],
                candidate["length"],
            )
        )
        return candidates

    @staticmethod
    def _records(source_records: List[Any]) -> List[Tuple[str, str, str]]:
        records: List[Tuple[str, str, str]] = []
        source_paths: Set[str] = set()
        source_record: Any
        for source_record in source_records:
            if not isinstance(source_record, dict):
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability received a non-object "
                    "lemmatized source record."
                )

            source_path: Any = source_record.get(
                EtlEventPayloadKeys.SOURCE_PATH
            )
            language: Any = source_record.get(
                EtlLanguageContract.RESULT_KEY
            )
            lemma_path: Any = source_record.get(
                EtlEventPayloadKeys.LEMMA
            )
            if not isinstance(source_path, str) or not source_path.strip():
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability requires every source "
                    "record to contain a non-empty source_path."
                )
            if not isinstance(language, str) or not language.strip():
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability requires every source "
                    "record to contain an identified language."
                )
            if not isinstance(lemma_path, str) or not lemma_path.strip():
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability requires every source "
                    "record to contain a non-empty lemma."
                )

            normalized_source_path: str = source_path.strip()
            if normalized_source_path in source_paths:
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability requires one "
                    f"lemmatized source record per file: '{source_path}'."
                )
            source_paths.add(normalized_source_path)

            normalized_language: str = language.strip().lower().replace("_", "-")
            if (
                normalized_language
                not in EtlLanguageContract.CODES.values()
            ):
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability received unsupported "
                    f"language '{language}'."
                )
            records.append(
                (
                    normalized_source_path,
                    normalized_language,
                    lemma_path.strip(),
                )
            )

        records.sort(key=lambda record: (record[0], record[1], record[2]))
        return records

    @staticmethod
    def _validate_tokens(
        tokens: List[str],
        token_entries: Dict[str, Any],
        source_path: str,
    ) -> None:
        token: str
        for token in tokens:
            if token not in token_entries:
                raise ValueError(
                    "ChunkCandidatesGeneratedCapability found token "
                    f"'{token}' from '{source_path}' absent from persisted "
                    "token statistics."
                )


class ChunkCandidateEventContract:
    """Validate freshness, deterministic identity and occurrence evidence."""

    @classmethod
    def is_valid(
        cls,
        event: Dict[str, Any],
        upstream_event: Dict[str, Any],
        generation_version: str,
        configuration: Dict[str, Any],
    ) -> bool:
        if event.get("state") != "chunk_candidates_generated":
            return False
        if event.get("chunk-candidate-generation-version") != generation_version:
            return False
        if not cls._has_current_provenance(event, upstream_event):
            return False

        candidate_data: Any = event.get("chunk_candidates")
        if not isinstance(candidate_data, dict):
            return False
        if candidate_data.get("configuration") != configuration:
            return False

        items: Any = candidate_data.get("items")
        if not isinstance(items, list):
            return False

        source_records_raw: Any = upstream_event["files"]
        if not isinstance(source_records_raw, list):
            return False
        source_records: List[Any] = source_records_raw

        token_statistics_raw: Any = upstream_event["token_statistics"]
        if not isinstance(token_statistics_raw, dict):
            return False
        token_statistics: Dict[str, Any] = token_statistics_raw

        expected_items: List[Dict[str, Any]] = ChunkCandidateGenerator.generate(
            source_records,
            token_statistics,
        )
        if items != expected_items:
            return False

        previous_sort_key: Optional[Tuple[str, str, int]] = None
        candidate: Any
        for candidate in items:
            if not isinstance(candidate, dict):
                return False
            if not cls._candidate_is_valid(candidate):
                return False

            language: str = candidate["language"]
            lemma: str = candidate["lemma"]
            length: int = candidate["length"]
            sort_key: Tuple[str, str, int] = (language, lemma, length)
            if previous_sort_key is not None and sort_key <= previous_sort_key:
                return False
            previous_sort_key = sort_key

        return True


    @classmethod
    def _candidate_is_valid(cls, candidate: Dict[str, Any]) -> bool:
        lemma: Any = candidate.get("lemma")
        tokens: Any = candidate.get("tokens")
        length: Any = candidate.get("length")
        language: Any = candidate.get("language")
        count: Any = candidate.get("count")
        file_frequency: Any = candidate.get("file_frequency")
        path_frequency: Any = candidate.get("path_frequency")
        occurrences: Any = candidate.get("occurrences")
        left_boundaries: Any = candidate.get("left_boundaries")
        right_boundaries: Any = candidate.get("right_boundaries")

        if not isinstance(lemma, str) or not lemma.strip():
            return False
        if not isinstance(language, str) or not language.strip():
            return False
        if not isinstance(tokens, list) or len(tokens) < 2:
            return False
        if any(not isinstance(token, str) or not token for token in tokens):
            return False
        if lemma != " ".join(tokens):
            return False
        if not isinstance(length, int) or isinstance(length, bool):
            return False
        if length != len(tokens):
            return False
        if language not in EtlLanguageContract.CODES.values():
            return False
        if not cls._positive_integer(count):
            return False
        if not cls._positive_integer(file_frequency):
            return False
        if not cls._positive_integer(path_frequency):
            return False
        if count < file_frequency or file_frequency < path_frequency:
            return False
        if not cls._boundaries_are_valid(left_boundaries, count):
            return False
        if not cls._boundaries_are_valid(right_boundaries, count):
            return False
        if not isinstance(occurrences, list) or len(occurrences) != count:
            return False

        return cls._occurrences_are_valid(
            occurrences,
            tokens,
            language,
            file_frequency,
            path_frequency,
        )

    @classmethod
    def _occurrences_are_valid(
        cls,
        occurrences: List[Any],
        tokens: List[str],
        language: str,
        file_frequency: int,
        path_frequency: int,
    ) -> bool:
        source_paths: Set[str] = set()
        lemma_paths: Set[str] = set()
        previous_key: Optional[Tuple[str, str, int, int]] = None
        occurrence: Any
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                return False
            source_path: Any = occurrence.get("source_path")
            source_id: Any = occurrence.get("source_id")
            lemma_path: Any = occurrence.get("lemma_path")
            occurrence_language: Any = occurrence.get("language")
            start: Any = occurrence.get("start")
            end: Any = occurrence.get("end")
            if not isinstance(source_path, str) or not source_path:
                return False
            if source_id != source_path:
                return False
            if not isinstance(lemma_path, str) or not lemma_path:
                return False
            if occurrence_language != language:
                return False
            if not isinstance(start, int) or isinstance(start, bool) or start < 0:
                return False
            if not isinstance(end, int) or isinstance(end, bool):
                return False
            if end != start + len(tokens):
                return False

            ordered_tokens: List[str]
            ordered_tokens, _ = TokenStatisticsTokenizer.tokenize(lemma_path)
            lemma_tokens: List[str] = ordered_tokens[1:-1]
            if end > len(lemma_tokens) or lemma_tokens[start:end] != tokens:
                return False

            occurrence_key: Tuple[str, str, int, int] = (
                source_path,
                lemma_path,
                start,
                end,
            )
            if previous_key is not None and occurrence_key < previous_key:
                return False
            previous_key = occurrence_key
            source_paths.add(source_path)
            lemma_paths.add(lemma_path)

        return (
            len(source_paths) == file_frequency
            and len(lemma_paths) == path_frequency
        )

    @staticmethod
    def _positive_integer(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1

    @classmethod
    def _boundaries_are_valid(
        cls,
        boundaries: Any,
        occurrence_count: int,
    ) -> bool:
        if not isinstance(boundaries, dict) or not boundaries:
            return False

        boundary_count: int = 0
        boundary: Any
        count: Any
        for boundary, count in boundaries.items():
            if not isinstance(boundary, str) or not boundary:
                return False
            if not cls._positive_integer(count):
                return False
            boundary_count += count

        return boundary_count == occurrence_count


class ChunkCandidatesGeneratedCapability(TransactionCapability):
    """Generate and persist traceable contiguous chunk candidates."""

    STATE_NAME: ClassVar[str] = "chunk_candidates_generated"
    CANDIDATES_KEY: ClassVar[str] = "chunk_candidates"
    ITEMS_KEY: ClassVar[str] = "items"
    GENERATION_VERSION_KEY: ClassVar[str] = (
        "chunk-candidate-generation-version"
    )
    GENERATION_VERSION: ClassVar[str] = "contiguous-ngram-1.0.0"
    ETL_EVENT_FILE_NAME: ClassVar[str] = f"{FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED.value}.json"

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "chunk_candidates_generated"
        ),
        version="1.0.0",
        name="Chunk Candidates Generated",
        description=(
            "Enumerate and persist every observed contiguous multi-token "
            "candidate with deterministic frequency and occurrence evidence."
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
                "event_path": {"type": "string"},
                "candidate_count": {"type": "integer"},
                CANDIDATES_KEY: {"type": "object"},
            },
        },
        log_message={
            "info": {
                "en": "Contiguous chunk candidates were generated.",
            },
            "debug_entry": {
                "en": "Generating chunk candidates from token statistics.",
            },
        },
    )

    @classmethod
    def configuration(cls) -> Dict[str, Any]:
        return {
            "minimum_length": ChunkCandidateGenerator.MINIMUM_LENGTH,
            "maximum_length": "source_path_token_count",
            "occurrence_offsets": "zero-based-half-open",
            "ordering": ["language", "lemma", "length"],
        }

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED.description(
                lang
            )
        )

    def is_satisfied(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context, EtlEventContextKeys.CONTAINER_PATH
        )
        if container_path_value is None:
            return False

        container_path: Path = Path(container_path_value).expanduser().resolve()
        if not self.event_path(container_path).is_file():
            return False

        event_content: str = StateWorkerAdapter.get_persisted_event(
            ChunkCandidatesGeneratedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED
        )

        event_data: Dict[str, Any] = json.loads(event_content)

        if EtlEventPayloadKeys.RO_CRATE_HASH not in event_data:
            return False

        if event_data[EtlEventPayloadKeys.RO_CRATE_HASH] != ContainerRoCrate.file_hash(container_path):
            return False

        return True

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, EtlEventContextKeys.CONTAINER_PATH)
        ).expanduser().resolve()

        token_statistics_content: str = StateWorkerAdapter.get_persisted_event(
            ChunkCandidatesGeneratedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED
        )

        lemmatized_path_content: str = StateWorkerAdapter.get_persisted_event(
            ChunkCandidatesGeneratedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.PATH_LEMMATIZED
        )

        token_statistics_data: Dict[str, Any] = json.loads(token_statistics_content)
        lemmatized_path_data: Dict[str, Any] = json.loads(lemmatized_path_content)

        source_records_raw: Any = lemmatized_path_data["files"]
        if not isinstance(source_records_raw, list):
            raise ValueError(
                "ChunkCandidatesGeneratedCapability requires persisted "
                "lemmatized source records."
            )
        source_records: List[Any] = source_records_raw

        token_statistics_raw: Any = token_statistics_data["token_statistics"]
        if not isinstance(token_statistics_raw, dict):
            raise ValueError(
                "ChunkCandidatesGeneratedCapability requires a persisted "
                "token_statistics object."
            )
        token_statistics: Dict[str, Any] = token_statistics_raw

        candidates: List[Dict[str, Any]] = ChunkCandidateGenerator.generate(
            source_records,
            token_statistics,
        )

        candidate_data: Dict[str, Any] = {
            "configuration": self.configuration(),
            self.ITEMS_KEY: candidates,
        }

        event: Dict[str, Any] = {
            **token_statistics_data,
            "state": FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED.value.strip(
                "_"
            ),
            self.GENERATION_VERSION_KEY: self.GENERATION_VERSION,
            self.CANDIDATES_KEY: candidate_data,
        }

        event_path: Path = self._write_event(container_path, event)

        return {
            "resulting_state": (
                FileMeaningSuggestionProcessState.CHUNK_CANDIDATES_GENERATED
            ),
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
        }

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
    def _write_event(
        cls,
        container_path: Path,
        event: Dict[str, Any],
    ) -> Path:
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
