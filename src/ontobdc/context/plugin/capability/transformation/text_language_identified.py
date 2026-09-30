from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import stanza
from stanza.models.common.doc import Document
from stanza.pipeline.core import Pipeline

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.dictionary_inspection_event import (
    DictionaryInspectionEtlStateAdapter,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.etl import EtlLanguageContract
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class TextLanguageIdentifiedCapability(TransactionCapability):
    """Identify the language of arbitrary normalized text."""

    INPUT_KEY: ClassVar[str] = "normalized_text"
    OUTPUT_KEY: ClassVar[str] = "language"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"
    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.TEXT_LANGUAGE_IDENTIFIED
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_language_identified"
        ),
        version="1.0.0",
        name="Text Language Identified",
        description=(
            "Identify the language of arbitrary normalized text for "
            "downstream lemmatization and semantic lookup."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "text", "language", "dictionary"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                INPUT_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "properties": {
                OUTPUT_KEY: {"type": "string"},
                EVENT_PATH_KEY: {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "Text language was identified."},
            "debug_entry": {"en": "Identifying normalized text language."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Idioma do Texto Identificado"
        return "Text Language Identified"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Identifica o idioma de texto normalizado arbitrario."
        return "Identify the language of arbitrary normalized text."

    def is_satisfied(self, context: CliContextPort) -> bool:
        if not context.has_parameter(self.OUTPUT_KEY):
            return False
        value: Any = context.get_parameter_value(self.OUTPUT_KEY)
        return (
            isinstance(value, str)
            and value in EtlLanguageContract.CODES.values()
            and DictionaryInspectionEtlStateAdapter.json_event_is_present(
                context=context,
                state=self.STATE,
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        normalized_text: str = RequiredParameter.of(context, self.INPUT_KEY)
        language: str = self._identify_language(normalized_text)
        context.set_parameter_value(self.OUTPUT_KEY, language)
        event_path: Path = DictionaryInspectionEtlStateAdapter.write_json(
            context=context,
            state=self.STATE,
            payload={
                self.INPUT_KEY: normalized_text,
                self.OUTPUT_KEY: language,
            },
        )
        context.set_parameter_value(self.EVENT_PATH_KEY, str(event_path))
        return {
            self.OUTPUT_KEY: language,
            self.EVENT_PATH_KEY: str(event_path),
        }

    @classmethod
    def _identify_language(cls, normalized_text: str) -> str:
        document: Document = cls._detector()(normalized_text)
        detected_language: Optional[str] = document.lang
        if detected_language not in EtlLanguageContract.CODES:
            raise ValueError(
                "Could not identify the language of normalized text "
                f"'{normalized_text}'."
            )
        return EtlLanguageContract.CODES[detected_language]

    @classmethod
    @lru_cache(maxsize=1)
    def _detector(cls) -> Pipeline:
        language_identifiers: List[str] = list(EtlLanguageContract.CODES)
        return stanza.Pipeline(
            lang="multilingual",
            processors="langid",
            langid_lang_subset=language_identifiers,
            verbose=False,
        )
