
import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set

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

class _TokenStatisticsComputer:
    """
    Accumulate token-level and corpus-level statistics across all source
    records of a container/scenario.

    One ``TokenStatisticsComputer`` instance is used per container: it
    receives each record exactly once through ``ingest``, then the
    complete serializable snapshot is obtained via ``snapshot``. Running
    ``ingest`` twice for the same logical container is a caller bug; the
    computer does not defend against double-counting because the
    capability recomputes from scratch every time (idempotency of the
    whole run, not incremental accumulation).
    """

    def __init__(self) -> None:
        self._source_record_count: int = 0
        self._token_occurrence_count: int = 0
        self._unique_lemma_paths: Set[str] = set()
        self._token_counts: Dict[str, int] = {}
        self._token_file_frequency: Dict[str, int] = {}
        self._token_path_frequency: Dict[str, int] = {}
        self._left_neighbors: Dict[str, Dict[str, int]] = {}
        self._right_neighbors: Dict[str, Dict[str, int]] = {}
        self._is_identifier: Dict[str, bool] = {}
        self._language_distribution: Dict[str, int] = {}
        self._tokens_seen_in_current_file: Set[str] = set()
        self._tokens_seen_in_current_path: Set[str] = set()
        self._current_lemma_path: Optional[str] = None

    def ingest(
        self,
        *,
        lemma: str,
        language: str,
    ) -> None:
        """
        Incorporate one lemmatized source record into the running totals.

        ``lemma`` is the complete lemmatized string (already validated as
        non-empty by the capability). ``language`` is the two-part code
        produced by the upstream language identification stage, and is
        only used for corpus-level language distribution.
        """
        ordered_tokens: List[str]
        identifier_map: Dict[str, bool]
        ordered_tokens, identifier_map = TokenStatisticsTokenizer.tokenize(lemma)

        self._source_record_count += 1
        self._language_distribution[language] = (
            self._language_distribution.get(language, 0) + 1
        )

        if lemma not in self._unique_lemma_paths:
            self._unique_lemma_paths.add(lemma)
            self._current_lemma_path = lemma
            self._tokens_seen_in_current_path = set()
        else:
            self._current_lemma_path = None
            self._tokens_seen_in_current_path = set()

        self._tokens_seen_in_current_file = set()

        token: str
        for token in ordered_tokens:
            if token in (
                TokenStatisticsTokenizer.BOS,
                TokenStatisticsTokenizer.EOS,
            ):
                continue

            self._token_occurrence_count += 1
            self._token_counts[token] = self._token_counts.get(token, 0) + 1

            if token not in self._is_identifier:
                self._is_identifier[token] = identifier_map.get(token, False)

            if token not in self._tokens_seen_in_current_file:
                self._tokens_seen_in_current_file.add(token)
                self._token_file_frequency[token] = (
                    self._token_file_frequency.get(token, 0) + 1
                )

            if self._current_lemma_path is not None:
                if token not in self._tokens_seen_in_current_path:
                    self._tokens_seen_in_current_path.add(token)
                    self._token_path_frequency[token] = (
                        self._token_path_frequency.get(token, 0) + 1
                    )

        index: int
        for index in range(1, len(ordered_tokens) - 1):
            left_token: str = ordered_tokens[index - 1]
            current_token: str = ordered_tokens[index]
            right_token: str = ordered_tokens[index + 1]

            right_bucket: Dict[str, int] = self._right_neighbors.setdefault(
                current_token, {}
            )
            right_bucket[right_token] = right_bucket.get(right_token, 0) + 1

            left_bucket: Dict[str, int] = self._left_neighbors.setdefault(
                current_token, {}
            )
            left_bucket[left_token] = left_bucket.get(left_token, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        """
        Return the complete serializable dictionary of statistics,
        shaped exactly as the ``token_statistics`` block the spec
        recommends plus identifier flags and language distribution.

        Dictionaries are emitted with ``sort_keys`` serialization so the
        persisted bytes are deterministic for any given corpus.
        """
        unique_tokens: Set[str] = set(self._token_counts.keys())
        sorted_tokens: List[str] = sorted(unique_tokens)

        tokens_payload: Dict[str, Dict[str, Any]] = {}
        token_value: str
        for token_value in sorted_tokens:
            left_sorted: Dict[str, int] = dict(
                sorted(self._left_neighbors.get(token_value, {}).items())
            )
            right_sorted: Dict[str, int] = dict(
                sorted(self._right_neighbors.get(token_value, {}).items())
            )
            tokens_payload[token_value] = {
                "count": self._token_counts[token_value],
                "file_frequency": self._token_file_frequency.get(token_value, 0),
                "path_frequency": self._token_path_frequency.get(token_value, 0),
                "is_identifier": self._is_identifier.get(token_value, False),
                "left_neighbors": left_sorted,
                "right_neighbors": right_sorted,
            }

        corpus_payload: Dict[str, Any] = {
            "source_record_count": self._source_record_count,
            "unique_lemma_path_count": len(self._unique_lemma_paths),
            "token_occurrence_count": self._token_occurrence_count,
            "unique_token_count": len(unique_tokens),
        }
        if len(self._language_distribution) > 1:
            corpus_payload["language_distribution"] = dict(
                sorted(self._language_distribution.items())
            )

        return {
            "corpus": corpus_payload,
            "tokens": tokens_payload,
        }


class TokenStatisticsComputedCapability(TransactionCapability):
    """
    Compute deterministic token-level corpus statistics over every
    lemmatized path the container's RO-Crate states, and persist the
    result as an ETL event file.

    This state is purely descriptive: it counts occurrences, files,
    unique paths, and immediate left/right neighbors for every token.
    No chunks, embeddings, ontology matches, or semantic inferences are
    produced here — those belong to later stages.
    """
    TOKEN_STATISTICS_KEY: ClassVar[str] = "token_statistics"
    LEMMATIZATION_VERSION_KEY: ClassVar[str] = "lemmatization-version"
    NORMALIZATION_VERSION_KEY: ClassVar[str] = "normalization-version"
    LANGUAGE_IDENTIFICATION_VERSION_KEY: ClassVar[str] = (
        "language-identification-version"
    )
    TOKEN_STATISTICS_VERSION_KEY: ClassVar[str] = "token-statistics-version"
    TOKEN_STATISTICS_VERSION: ClassVar[str] = "1.0.0"
    TOKENIZER_VERSION_KEY: ClassVar[str] = "tokenizer-version"
    TOKENIZER_VERSION: ClassVar[str] = "whitespace-split-identifier-pattern-1.0.0"

    ETL_EVENT_FILE_NAME: ClassVar[str] = (
        f"{FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED.value}.json"
    )

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.suggest.plugin.capability.transformation.target."
            "token_statistics_computed"
        ),
        version="1.0.0",
        name="Token Statistics Computed",
        description=(
            "Compute deterministic token-level corpus statistics over "
            "every lemmatized file path stated by a container's RO-Crate, "
            "and persist the result as an ETL event file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=[
            "suggestion",
            "file",
            "lemma",
            "token",
            "statistics",
            "corpus",
            "etl",
        ],
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
                "token_statistics": {
                    "type": "object",
                },
            },
        },
        log_message={
            "info": {
                "en": (
                    "Token-level corpus statistics were computed for "
                    "every lemmatized file path."
                ),
            },
            "debug_entry": {
                "en": (
                    "Computing token-level corpus statistics over every "
                    "lemmatized file path."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED.description(
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
            TokenStatisticsComputedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED
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

        event_content: str = StateWorkerAdapter.get_persisted_event(
            TokenStatisticsComputedCapability.event_path(container_path).parent,
            FileMeaningSuggestionProcessState.PATH_LEMMATIZED,
        )

        event_data: Dict[str, Any] = json.loads(event_content)
        lemma_files_raw: Any = event_data["files"]
        if not isinstance(lemma_files_raw, list):
            raise ValueError(
                "TokenStatisticsComputedCapability requires a path-lemmatized "
                "event containing a file list."
            )
        lemma_files: List[Dict[str, Any]] = lemma_files_raw

        computer: _TokenStatisticsComputer = _TokenStatisticsComputer()

        file_entry: Any
        for file_entry in lemma_files:
            if not isinstance(file_entry, dict):
                raise ValueError(
                    "TokenStatisticsComputedCapability received a non-object "
                    "entry in the path-lemmatized file list."
                )
            lemma_raw: Any = file_entry[EtlEventPayloadKeys.LEMMA]
            if not isinstance(lemma_raw, str) or not lemma_raw.strip():
                raise ValueError(
                    "TokenStatisticsComputedCapability requires every file "
                    "entry to contain a non-empty lemma produced by the "
                    "upstream lemmatization stage."
                )
            language_raw: Any = file_entry[EtlLanguageContract.RESULT_KEY]
            if not isinstance(language_raw, str) or not language_raw.strip():
                raise ValueError(
                    "TokenStatisticsComputedCapability requires every file "
                    "entry to carry an identified language."
                )

            computer.ingest(lemma=lemma_raw, language=language_raw)

        token_statistics: Dict[str, Any] = computer.snapshot()

        event: Dict[str, Any] = {
            **event_data,
            "state": (
                FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED.value.strip(
                    "_"
                )
            ),
            self.TOKEN_STATISTICS_VERSION_KEY: self.TOKEN_STATISTICS_VERSION,
            self.TOKENIZER_VERSION_KEY: self.TOKENIZER_VERSION,
            self.TOKEN_STATISTICS_KEY: token_statistics,
        }

        event_path: Path = self._write_event(container_path, event)

        return {
            "resulting_state": (
                FileMeaningSuggestionProcessState.TOKEN_STATISTICS_COMPUTED
            ),
            EtlEventContextKeys.CONTAINER_PATH: str(container_path),
            "event_path": str(event_path),
        }


    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        """
        Return where this capability's own event lives.

        Public because downstream pipeline stages (chunk candidates,
        ontology matching) will read back the token statistics the same
        way the lemmatization stage reads the normalization event.
        """
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
        """
        Atomically write the ETL event file (temp file, then replace) so
        a reader never observes a partially written event.
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
