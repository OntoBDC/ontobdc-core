from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

import stanza
from stanza.models.common.doc import Document, Sentence, Word
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


class TextLemmatizedCapability(TransactionCapability):
    """Lemmatize arbitrary normalized text using its detected language."""

    TEXT_KEY: ClassVar[str] = "normalized_text"
    LANGUAGE_KEY: ClassVar[str] = "language"
    OUTPUT_KEY: ClassVar[str] = "lemma"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"
    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.TEXT_LEMMATIZED
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_lemmatized"
        ),
        version="1.0.0",
        name="Text Lemmatized",
        description=(
            "Reduce arbitrary normalized text to language-aware lemmas for "
            "semantic dictionary resolution."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "text", "lemma", "dictionary"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                TEXT_KEY: {"type": "string", "required": True},
                LANGUAGE_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={
            "properties": {
                OUTPUT_KEY: {"type": "string"},
                EVENT_PATH_KEY: {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "Text was lemmatized."},
            "debug_entry": {"en": "Lemmatizing normalized text."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Texto Lematizado"
        return "Text Lemmatized"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Reduz texto normalizado a lemas dependentes do idioma."
        return "Reduce normalized text to language-aware lemmas."

    def is_satisfied(self, context: CliContextPort) -> bool:
        if not context.has_parameter(self.OUTPUT_KEY):
            return False
        value: Any = context.get_parameter_value(self.OUTPUT_KEY)
        return (
            isinstance(value, str)
            and bool(value.strip())
            and DictionaryInspectionEtlStateAdapter.json_event_is_present(
                context=context,
                state=self.STATE,
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        normalized_text: str = RequiredParameter.of(context, self.TEXT_KEY)
        language: str = RequiredParameter.of(context, self.LANGUAGE_KEY)
        if language not in EtlLanguageContract.CODES.values():
            raise ValueError(f"Unsupported language '{language}'.")
        lemma: str = self._lemmatize(normalized_text, language)
        context.set_parameter_value(self.OUTPUT_KEY, lemma)
        event_path: Path = DictionaryInspectionEtlStateAdapter.write_json(
            context=context,
            state=self.STATE,
            payload={
                self.TEXT_KEY: normalized_text,
                self.LANGUAGE_KEY: language,
                self.OUTPUT_KEY: lemma,
            },
        )
        context.set_parameter_value(self.EVENT_PATH_KEY, str(event_path))
        return {
            self.OUTPUT_KEY: lemma,
            self.EVENT_PATH_KEY: str(event_path),
        }

    @classmethod
    def _lemmatize(cls, value: str, language: str) -> str:
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
                        f"'{word.text}' in text '{value}'."
                    )
                lemmas.append(lemma.strip().lower())
        result: str = " ".join(lemmas)
        if not result:
            raise ValueError("Text lemmatization produced an empty value.")
        return result

    @classmethod
    @lru_cache(maxsize=8)
    def _language_pipeline(cls, language: str) -> Pipeline:
        normalized_language: str = language.strip().lower().split("-", 1)[0]
        return stanza.Pipeline(
            lang=normalized_language,
            processors="tokenize,mwt,pos,lemma",
            verbose=False,
        )
