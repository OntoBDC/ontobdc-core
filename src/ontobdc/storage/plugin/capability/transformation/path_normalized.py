
import re
import json
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.storage.adapter.crate import ContainerRoCrate
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.plugin.machine.file_meaning_suggestion.state import FileMeaningSuggestionProcessState

from ontobdc.storage.plugin.capability.transformation import (
    CONTAINER_PATH_KEY,
    RO_CRATE_HASH_KEY,
    SOURCE_PATH_RESULT_KEY,
    ETL_MODULE_NAME,
    ETL_PHASE_NAME,
    ETL_ENTITY_NAME,
    WHITESPACE_PATTERN,
    ETL_DIRECTORY_NAME,
    NORMALIZED_PATH_RESULT_KEY,
)


class PathNormalizedCapability(TransactionCapability):
    """
    Normalizes every file the container's RO-Crate states, and persists
    the result as an ETL event file.

    The event layout (``.__ontobdc__/etl/<phase>/<entity>/<state>.json``)
    mirrors the one the removed ``EntityLearningStepRepository`` family
    used for the context-learning ETL (``.__ontobdc__/etl/learning/entity``,
    ``.../analysis/entity``, ``.../import/document``): a durable, on-disk
    record of what a pipeline step produced, kept next to the container's
    other OntoBDC-managed files.
    """
    NORMALIZATION_VERSION_KEY: ClassVar[str] = "normalization-version"
    NORMALIZATION_VERSION: ClassVar[str] = "1.0.0"
    PATH_SEPARATOR_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"[\\/_-]+"
    )
    REMOVED_CHARACTER_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"[()%|{}#!]"
    )

    ETL_EVENT_FILE_NAME: ClassVar[str] = f"{FileMeaningSuggestionProcessState.PATH_NORMALIZED.value}.json"

    METADATA = CapabilityMetadata(
        id="org.ontobdc.suggest.plugin.capability.transformation.target.path_normalized",
        version="1.0.0",
        name="Path Normalized",
        description=(
            "Normalize every file path stated by a container's RO-Crate "
            "into a text representation suitable for semantic processing, "
            "and persist the result as an ETL event file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["suggestion", "file", "path", "normalization", "etl"],
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
                    "Every file the RO-Crate states had its path normalized "
                    "for semantic processing."
                ),
            },
            "debug_entry": {
                "en": (
                    "Normalizing every file path the container's RO-Crate "
                    "states."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_NORMALIZED.label(lang)

    def description(self, lang: str = "en") -> str:
        return FileMeaningSuggestionProcessState.PATH_NORMALIZED.description(lang)

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
            FileMeaningSuggestionProcessState.PATH_NORMALIZED
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

        source_paths: List[str] = ContainerRoCrate.file_paths(container_path)
        files: List[Dict[str, str]] = [
            {
                SOURCE_PATH_RESULT_KEY: source_path,
                NORMALIZED_PATH_RESULT_KEY: self._normalize(source_path),
            }
            for source_path in source_paths
        ]

        event_path: Path = self._write_event(container_path, files)

        return {
            "resulting_state": FileMeaningSuggestionProcessState.PATH_NORMALIZED,
            CONTAINER_PATH_KEY: str(container_path),
            "event_path": str(event_path),
        }

    @classmethod
    def _normalize(cls, path: str) -> str:
        path_without_extension: str = str(PurePosixPath(path).with_suffix(""))
        normalized_unicode: str = unicodedata.normalize("NFKC", path_without_extension)
        normalized_case: str = normalized_unicode.casefold()
        separated_text: str = cls.PATH_SEPARATOR_PATTERN.sub(
            " ",
            normalized_case,
        )
        text_without_removed_characters: str = (
            cls.REMOVED_CHARACTER_PATTERN.sub(" ", separated_text)
        )

        return WHITESPACE_PATTERN.sub(
            " ", text_without_removed_characters
        ).strip()

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        """
        Return where this capability's own event lives.

        Public because it is also how a later pipeline stage (e.g.
        PathLemmatizedCapability) reads back what path normalization
        produced, not only how this capability checks its own
        ``is_satisfied``.
        """
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
        files: List[Dict[str, str]],
    ) -> Path:
        """
        Atomically write the ETL event file (temp file, then replace) so a
        reader never observes a partially written event.
        """
        event_path: Path = cls.event_path(container_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)

        event: Dict[str, Any] = {
            "state": FileMeaningSuggestionProcessState.PATH_NORMALIZED.value.strip(
                "_"
            ),
            CONTAINER_PATH_KEY: str(container_path),
            RO_CRATE_HASH_KEY: ContainerRoCrate.file_hash(container_path),
            cls.NORMALIZATION_VERSION_KEY: cls.NORMALIZATION_VERSION,
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
