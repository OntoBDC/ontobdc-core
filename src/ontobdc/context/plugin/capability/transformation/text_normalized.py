import unicodedata
from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.adapter.dictionary_inspection_event import (
    DictionaryInspectionEtlStateAdapter,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class TextNormalizedCapability(TransactionCapability):
    """Normalize arbitrary text for downstream semantic resolution."""

    INPUT_KEY: ClassVar[str] = "text"
    OUTPUT_KEY: ClassVar[str] = "normalized_text"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"
    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.TEXT_NORMALIZED
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_normalized"
        ),
        version="1.0.0",
        name="Text Normalized",
        description=(
            "Normalize arbitrary text into a deterministic representation "
            "for language identification, lemmatization and semantic lookup."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "text", "normalization", "dictionary"],
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
            "info": {"en": "Text was normalized for semantic resolution."},
            "debug_entry": {"en": "Normalizing text for semantic resolution."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Texto Normalizado"
        return "Text Normalized"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Normaliza texto arbitrario para resolucao semantica."
        return "Normalize arbitrary text for semantic resolution."

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
        source: str = RequiredParameter.of(context, self.INPUT_KEY)
        normalized: str = self.normalize(source)
        context.set_parameter_value(self.OUTPUT_KEY, normalized)
        event_path: Path = DictionaryInspectionEtlStateAdapter.write_json(
            context=context,
            state=self.STATE,
            payload={
                self.INPUT_KEY: source,
                self.OUTPUT_KEY: normalized,
            },
        )
        context.set_parameter_value(self.EVENT_PATH_KEY, str(event_path))
        return {
            self.OUTPUT_KEY: normalized,
            self.EVENT_PATH_KEY: str(event_path),
        }

    @staticmethod
    def normalize(value: str) -> str:
        stripped: str = value.strip()
        if not stripped:
            raise ValueError("TextNormalizedCapability requires non-empty text.")
        casefolded: str = stripped.casefold()
        decomposed: str = unicodedata.normalize("NFKD", casefolded)
        no_marks: str = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        collapsed: str = " ".join(no_marks.split())
        if not collapsed:
            raise ValueError("Text normalization produced an empty value.")
        return collapsed
