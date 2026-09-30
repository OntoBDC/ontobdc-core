import json
import hashlib
from enum import Enum
from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class DictionaryInspectionEtlStateAdapter:
    """
    Persist dictionary-inspection ETL state artifacts.

    Artifacts are grouped in a directory named by the SHA-256 hash of the
    inspected term, so each term keeps its own run. The basename of every
    artifact is exactly ``state.value``, so a state ``__text_normalized__``
    is persisted as ``<term hash>/__text_normalized__.json``.
    """

    MODULE_NAME: ClassVar[str] = "context"
    ACTION_NAME: ClassVar[str] = "inspection"
    ENTITY_NAME: ClassVar[str] = "dictionary"
    JSON_EXTENSION: ClassVar[str] = "json"
    MARKDOWN_EXTENSION: ClassVar[str] = "md"
    TERM_KEY: ClassVar[str] = "text"

    @classmethod
    def event_path(
        cls,
        context: CliContextPort,
        state: Enum,
        extension: str,
    ) -> Path:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        return (
            StorageBootstrap.get_ontobdc_directory(root_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / cls.MODULE_NAME
            / cls.ACTION_NAME
            / cls.ENTITY_NAME
            / cls.term_hash(context)
            / f"{state.value}.{extension}"
        )

    @classmethod
    def term_hash(cls, context: CliContextPort) -> str:
        term: str = RequiredParameter.of(context, cls.TERM_KEY)
        return hashlib.sha256(term.encode("utf-8")).hexdigest()

    @classmethod
    def write_json(
        cls,
        context: CliContextPort,
        state: Enum,
        payload: Dict[str, Any],
    ) -> Path:
        event: Dict[str, Any] = {
            "state": state.value,
            **payload,
        }
        serialized: str = json.dumps(
            event,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        return cls._write(
            cls.event_path(context, state, cls.JSON_EXTENSION),
            serialized + "\n",
        )

    @classmethod
    def write_markdown(
        cls,
        context: CliContextPort,
        state: Enum,
        markdown: str,
    ) -> Path:
        return cls._write(
            cls.event_path(context, state, cls.MARKDOWN_EXTENSION),
            markdown + "\n",
        )

    @classmethod
    def json_event_is_present(
        cls,
        context: CliContextPort,
        state: Enum,
    ) -> bool:
        event_path: Path = cls.event_path(context, state, cls.JSON_EXTENSION)
        if not event_path.is_file():
            return False
        event: Dict[str, Any] = json.loads(event_path.read_text(encoding="utf-8"))
        return event["state"] == state.value

    @classmethod
    def markdown_event_is_present(
        cls,
        context: CliContextPort,
        state: Enum,
    ) -> bool:
        return cls.event_path(context, state, cls.MARKDOWN_EXTENSION).is_file()

    @staticmethod
    def _write(event_path: Path, content: str) -> Path:
        event_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path = event_path.with_name(f".{event_path.name}.tmp")
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(event_path)
        return event_path
