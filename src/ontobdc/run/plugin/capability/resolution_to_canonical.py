
from typing import Any, Dict, List
from spellchecker import SpellChecker
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.resource.capability import TransformationCapability, CapabilityMetadata


class ResolutionToCanonicalCapability(TransformationCapability):
    """
    Capability for resolving user intent to canonical form.
    """
    METADATA = CapabilityMetadata(
        id="org.ontobdc.run.plugin.capability.resolution.target.canonical",
        version="0.1.0",
        name="Intent Canonical Resolution",
        description="Resolve user intent to canonical form.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags={
            "en": ["data", "intent", "canonical", "resolution"],
            "pt": ["dados", "intenção", "canônico", "resolução"],
        },
        supported_languages=["en", "pt"],
        input_schema={
            "type": "object",
            "properties": {},
        },
        output_schema={
            "type": "object",
            "properties": {
                "cli_context": {
                    "type": CliContextPort,
                    "description": "The updated context port with canonical intent.",
                },
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        """
        Returns the human-friendly label in the specified language.
        """
        labels = {
            "en": "Intent Canonical Resolution",
            "pt": "Resolução Canônica de Intenção",
        }
        return labels.get(lang, labels["en"])

    def description(self, lang: str = "en") -> str:
        """
        Returns the description in the specified language.
        """
        descriptions = {
            "en": "Resolve user intent to canonical form.",
            "pt": "Resolve a intenção do usuário para forma canônica.",
        }
        return descriptions.get(lang, descriptions["en"])

    @property
    def _spacy_models(self) -> Dict[str, str]:
        return {
            "en": "en_core_web_md",
            "pt": "pt_core_news_md",
        }

    def _load_spacy_model(self, lang: str) -> Any:
        try:
            import spacy
        except ImportError:
            raise ImportError("spaCy is required for intent parsing. Install with 'pip install spacy' and download a model with 'python -m spacy download en_core_web_md' or 'python -m spacy download pt_core_news_md'.")

        model_name = self._spacy_models.get(lang, self._spacy_models)

        try:
            return spacy.load(model_name)
        except OSError:
            raise ImportError(f"spaCy model '{model_name}' not found. Install it with 'python -m spacy download {model_name}'.")

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability to resolve user intent to canonical form.
        :param context: The context port for interaction with the environment.
        :return: A dictionary containing the updated context.
        """
        user_intent: str = context.get_parameter_value("user_intent")

        spell = SpellChecker(language=context.language)
        nlp = self._load_spacy_model(context.language)

        corrected_intent: List[str] = []
        for token in nlp(user_intent):
            # if not token.is_punct:
            token_text: str = spell.correction(token.text)
            corrected_intent.append(token_text)
            continue

        canonical_intent: List[str] = []
        for token in nlp(' '.join(corrected_intent)):
            if not token.is_stop and not token.is_punct:
                canonical_intent.append(token.lemma_)

        context.set_parameter_value("canonical_intent", ';'.join(canonical_intent))

        return {
            "cli_context": context,
        }


