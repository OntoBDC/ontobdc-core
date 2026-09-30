from typing import Any, ClassVar, Dict, List
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.adapter.kind_representation import (
    OntologyKindRepresentationResolver,
)
from ontobdc.context.adapter.dictionary_inspection_event import (
    DictionaryInspectionEtlStateAdapter,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)


class KindRepresentationResolvedCapability(TransactionCapability):
    """
    Fetch the representations declared for every resolved ontology term.

    The output maps the IRI of each exact match or candidate to its
    representations, each with its JSON-LD definition. A term without a
    declared representation is recorded with an empty list.
    """

    RESOLUTION_KEY: ClassVar[str] = "ontology_term_resolution"
    OUTPUT_KEY: ClassVar[str] = "kind_representations"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"
    MATCH_KEYS: ClassVar[Dict[str, str]] = {
        "exact": "exact_matches",
        "fuzzy-substring": "candidates",
    }
    STATE: ClassVar[DictionaryInspectionProcessState] = (
        DictionaryInspectionProcessState.KIND_REPRESENTATION_RESOLVED
    )

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "kind_representation_resolved"
        ),
        version="1.0.0",
        name="Kind Representation Resolved",
        description=(
            "Fetch the representations declared in the kind representation "
            "ontologies for every resolved ontology term."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "ontology", "dictionary", "representation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                RESOLUTION_KEY: {"type": "object", "required": True},
            },
        },
        output_schema={
            "properties": {
                OUTPUT_KEY: {"type": "object"},
                EVENT_PATH_KEY: {"type": "string"},
            },
        },
        log_message={
            "info": {"en": "Kind representations were resolved."},
            "debug_entry": {"en": "Resolving kind representations."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Representacao do Tipo Resolvida"
        return "Kind Representation Resolved"

    def description(self, lang: str = "en") -> str:
        if lang.strip().lower().replace("_", "-") == "pt-br":
            return "Busca as representacoes declaradas para os termos resolvidos."
        return "Fetch the representations declared for the resolved terms."

    def is_satisfied(self, context: CliContextPort) -> bool:
        return context.has_parameter(
            self.OUTPUT_KEY
        ) and DictionaryInspectionEtlStateAdapter.json_event_is_present(
            context=context,
            state=self.STATE,
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        resolution: Any = context.get_parameter_value(self.RESOLUTION_KEY)
        if not isinstance(resolution, dict):
            raise ValueError(
                f"Context parameter '{self.RESOLUTION_KEY}' must be an object."
            )
        match_type: str = resolution["match_type"]
        if match_type not in self.MATCH_KEYS:
            raise ValueError(f"Unsupported ontology match type '{match_type}'.")

        resolver: OntologyKindRepresentationResolver = (
            OntologyKindRepresentationResolver.from_configuration()
        )
        kind_representations: Dict[str, List[Dict[str, Any]]] = {}
        term: Dict[str, Any]
        for term in resolution[self.MATCH_KEYS[match_type]]:
            kind_representations[term["iri"]] = resolver.representations_of(
                term["iri"]
            )

        context.set_parameter_value(self.OUTPUT_KEY, kind_representations)
        event_path: Path = DictionaryInspectionEtlStateAdapter.write_json(
            context=context,
            state=self.STATE,
            payload={self.OUTPUT_KEY: kind_representations},
        )
        context.set_parameter_value(self.EVENT_PATH_KEY, str(event_path))
        return {
            self.OUTPUT_KEY: kind_representations,
            self.EVENT_PATH_KEY: str(event_path),
        }
