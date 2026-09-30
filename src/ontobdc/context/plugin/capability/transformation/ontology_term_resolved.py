from typing import Any, ClassVar, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.adapter.ontology_term_resolution import OntologyTermResolver
from ontobdc.context.adapter.dictionary_inspection_event import (
    DictionaryInspectionEtlStateAdapter,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)


class OntologyTermResolvedCapability(TransactionCapability):
    """
    Resolve a lemma against the ontology dictionary.

    The resolution is either a set of exact matches or, only when there is
    no exact match, a scored candidate list. The two contracts differ on
    purpose and are persisted as the ``__ontology_term_resolved__`` state.
    """

    LEMMA_KEY: ClassVar[str] = "lemma"
    LANGUAGE_KEY: ClassVar[str] = "language"
    OUTPUT_KEY: ClassVar[str] = "ontology_term_resolution"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"
    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.ONTOLOGY_TERM_RESOLVED
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "ontology_term_resolved"
        ),
        version="1.3.0",
        name="Ontology Term Resolved",
        description=(
            "Resolve lemmatized text as exact ontology matches or, when none "
            "exist, deterministic fuzzy candidates."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "ontology", "dictionary", "resolution"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                LEMMA_KEY: {"type": "string", "required": True},
                LANGUAGE_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={
            "properties": {
                OUTPUT_KEY: {"type": "object"},
                EVENT_PATH_KEY: {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "Ontology dictionary term resolution completed."},
            "debug_entry": {"en": "Resolving text against ontology terms."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Termo da Ontologia Resolvido"
        return "Ontology Term Resolved"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Resolve texto como correspondencias exatas ou candidatos."
        return "Resolve text as exact matches or candidate matches."

    def is_satisfied(self, context: CliContextPort) -> bool:
        return context.has_parameter(
            self.OUTPUT_KEY
        ) and DictionaryInspectionEtlStateAdapter.json_event_is_present(
            context=context,
            state=self.STATE,
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        lemma: str = RequiredParameter.of(context, self.LEMMA_KEY)
        language: str = RequiredParameter.of(context, self.LANGUAGE_KEY)
        resolution: Dict[str, Any] = OntologyTermResolver.from_configuration().resolve(
            lemma=lemma,
            language=language,
        )
        context.set_parameter_value(self.OUTPUT_KEY, resolution)
        event_path: Path = DictionaryInspectionEtlStateAdapter.write_json(
            context=context,
            state=self.STATE,
            payload={
                self.LEMMA_KEY: lemma,
                self.LANGUAGE_KEY: language,
                self.OUTPUT_KEY: resolution,
            },
        )
        context.set_parameter_value(self.EVENT_PATH_KEY, str(event_path))
        return {
            self.OUTPUT_KEY: resolution,
            self.EVENT_PATH_KEY: str(event_path),
        }
