
import os
import json
from typing import Any, Dict, List
from ontobdc.cli import get_config_dir
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.run.adapter.spacy import SpacyIntentModelResolver
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.run.domain.port.intent import IntentModelResolverPort
from ontobdc.run.domain.exception.intent import IntentLanguageNotSupportedException
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class ResolutionToParsedCapability(TransformationCapability):
    """
    Capability for parsing user intent and confirming it.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.parsed",
        version="0.1.0",
        name="Intent Parsing",
        description="Parse user intent and confirm it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "parsing", "intent", "resolution"],
            "pt_BR": ["dados", "analise", "intenção", "resolução"],
        },
        supported_languages=["en", "pt_BR"],
        input_schema={
            "type": "object",
            "properties": {},
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
        raises=[
            {
                "code": "intent_language_not_supported",
                "python_type": IntentLanguageNotSupportedException,
                "identifier": "org.ontobdc.domain.resource.capability.exception.intent.language_not_supported",
                "description": "Language not supported for intent parsing.",
            },
        ],
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Intent Parsing",
            "pt_BR": "Análise de Intenção",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Parse user intent and confirm it.",
            "pt_BR": "Analise a intenção do usuário e confirme.",
        }
        return descriptions.get(lang, descriptions["en"])

    def _confirm_text(self, lang: str = "en") -> str:
        """
        Returns the confirmation prompt text in the specified language.
        """
        prompts = {
            "en": "Is this correct?",
            "pt_BR": "Isso está correto?",
        }

        return prompts.get(lang, prompts["en"])

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to parse user intent.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the updated context.
        """
        user_intent: str = context.get_parameter_value("user_intent")

        try:
            model_resolver: IntentModelResolverPort = SpacyIntentModelResolver(context.language)
            parsed_result: IntentScoreResponse = model_resolver.parse_intent(user_intent)

            parsed_intent_file: str = os.path.join(get_config_dir(), IntentScoreResponse.PARSED_INTENT_FILE_NAME)
            if os.path.exists(parsed_intent_file):
                os.remove(parsed_intent_file)

            if not hasattr(parsed_result, 'score'):
                raise ValueError("IntentScoreResponse must have a score attribute.")

            if not isinstance(parsed_result.score, (int, float)):
                raise ValueError("IntentScoreResponse score must be a number.")

            parsed_result_roots: List[Dict[str, Any]] = []
            for root in parsed_result.roots:
                if root['pos'] == 'NOUN':
                    parsed_result_roots.append(root)

            with open(parsed_intent_file, "w") as f:
                json.dump(parsed_result.serialize(), f, ensure_ascii=False, indent=4)

            if not parsed_result_roots:
                context.set_parameter_value("intent_score", .0)
                return {
                    "cli_context": context,
                }

            # if parsed_result.score >= IntentScoreResponse.INTENT_SCORE_THRESHOLD:
                # raise ValueError(f"IntentScoreResponse score must be at least {IntentScoreResponse.INTENT_SCORE_THRESHOLD}")

            context.set_parameter_value("intent_score", parsed_result.score)

        except ImportError as e:
            if "spaCy" in str(e) and "core_news_md" in str(e):
                raise IntentLanguageNotSupportedException(f"Language '{context.language}' is not supported for intent parsing.")

            raise e

        return {
            "cli_context": context,
        }
