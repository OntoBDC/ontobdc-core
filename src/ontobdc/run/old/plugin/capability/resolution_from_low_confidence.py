
import os
import json
from ontobdc.cli import get_config_dir
from typing import Any, Dict, List, Type
from ontobdc.shared.adapter.plugin import CapabilityLoader
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.run.adapter.spacy import SpacyIntentModelResolver
from ontobdc.run.domain.port.intent import IntentModelResolverPort
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.run.domain.exception.intent import NoValidCapabilitiesException, IntentScoreTooLowException
from ontobdc.shared.domain.resource.capability import Capability, QueryCapability, TransactionCapability, TransformationCapability, CapabilityMetadata


class ResolutionFromLowConfidenceCapability(TransformationCapability):
    """
    Capability for resolving low-confidence parsed intents by suggesting capability matches
    based on exact lemma-to-tag matches before asking the user to reformulate the request.
    """

    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.from.low_confidence",
        version="0.1.0",
        name="Low Confidence Intent Resolution",
        description="Suggest likely capabilities when the parsed intent score is insufficient.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "low confidence", "intent", "resolution"],
            "pt": ["dados", "baixa confianca", "intencao", "resolucao"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {
                "parsed_intent": {
                    "type": IntentScoreResponse,
                    "uri": "http://ontobdc.org/ontology/domain/ns.ttl#parsedIntent",
                    "required": True,
                    "description": "The parsed intent with score and linguistic analysis.",
                }
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "cli_context": {
                    "type": CliContextPort,
                    "description": "The updated context port.",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        labels = {
            "en": "Low Confidence Intent Resolution",
            "pt": "Resolucao de Intencao com Baixa Confianca",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        descriptions = {
            "en": "Suggest likely capabilities when the parsed intent score is insufficient.",
            "pt": "Sugere capabilities provaveis quando o score da intenção analisada e insuficiente.",
        }
        return descriptions.get(lang, descriptions["en"])

    def _find_matching_capabilities(self, parsed_intent: IntentScoreResponse, lang: str) -> List[Type[Capability]]:
        lemmas = {
            str(root.get("lemma", "")).strip().lower()
            for root in parsed_intent.roots
            if str(root.get("lemma", "")).strip()
        }
        if not lemmas:
            return []

        matching_capabilities: List[Type[Capability]] = []
        for capability in CapabilityLoader().get_all("capability"):
            if issubclass(capability, TransformationCapability):
                continue
            if not issubclass(capability, (QueryCapability, TransactionCapability)):
                continue

            capability_instance = capability()
            tags = {
                str(tag).strip().lower()
                for tag in capability_instance.tags(lang)
                if str(tag).strip()
            }

            if lemmas.intersection(tags):
                matching_capabilities.append(capability)

        return matching_capabilities

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Execute the capability.
        """
        user_intent: str = context.get_parameter_value("user_intent")
        canonical_intent: str = context.get_parameter_value("canonical_intent")

        model_resolver: IntentModelResolverPort = SpacyIntentModelResolver(context.language)
        parsed_result: IntentScoreResponse = model_resolver.parse_intent(canonical_intent.replace(";", " "))

        parsed_intent_file: str = os.path.join(get_config_dir(), IntentScoreResponse.CANONICALIZED_INTENT_FILE_NAME)
        if os.path.exists(parsed_intent_file):
            os.remove(parsed_intent_file)

        parsed_result_roots: List[Dict[str, Any]] = []
        for root in parsed_result.roots:
            if root['pos'] == 'NOUN':
                parsed_result_roots.append(root)

        with open(parsed_intent_file, "w") as f:
            json.dump(parsed_result.serialize(), f, ensure_ascii=False, indent=4)

        if not parsed_result_roots or len(parsed_result_roots) > 1:
            raise IntentScoreTooLowException(f"The user intent {user_intent} has an insufficient confidence score.")

        matching_capabilities: List[Type[Capability]] = self._find_matching_capabilities(parsed_result, context.language)
        if not matching_capabilities:
            raise NoValidCapabilitiesException(f"The user intent {user_intent} could not be resolved to any capability.")

        for candidate in matching_capabilities:
            parsed_result.matching_capabilities.append(candidate.METADATA.id)

        with open(parsed_intent_file, "w") as f:
            json.dump(parsed_result.serialize(), f, ensure_ascii=False, indent=4)

        context.set_parameter_value("intent_score", .8)

        return {
            "cli_context": context,
        }
