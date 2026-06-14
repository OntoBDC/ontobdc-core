
from typing import Dict, Any
from spacy.tokens import Token
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.run.domain.port.intent import IntentModelResolverPort

OLIA = get_ontology_by_prefix("olia")


class SpacyIntentModelResolver(IntentModelResolverPort):

    MAPPER_OLIA = {
        # Interrogative Pronouns (e.g., "Quais", "What")
        ("PRON", "PronType=Int"): OLIA["InterrogativePronoun"],
        ("DET", "PronType=Int"): OLIA["InterrogativePronoun"],
        
        # Interrogative Adverbs (e.g., "Onde", "Quando", "Where")
        ("ADV", "PronType=Int"): OLIA["InterrogativeAdverb"],
        
        # Base classes for fallbacks or normal structures
        ("NOUN", None): OLIA["Noun"],
        ("VERB", None): OLIA["Verb"],
        ("PRON", None): OLIA["Pronoun"],
        ("ADV", None): OLIA["Adverb"],
        ("PUNCT", None): OLIA["Punctuation"],
    }

    def __init__(self, lang: str):
        self.lang = lang
        self._nlp = self._load_spacy_model(lang)

    @property
    def models(self) -> Dict[str, str]:
        return {
            "en": "en_core_web_md",
            "pt": "pt_core_news_md",
            "pt_BR": "pt_core_news_md",
        }

    def _load_spacy_model(self, lang: str) -> Any:
        try:
            import spacy
        except ImportError:
            raise ImportError("spaCy is required for intent parsing. Install with 'pip install spacy' and download a model with 'python -m spacy download en_core_web_md' or 'python -m spacy download pt_core_news_md'.")

        model_name = self.models.get(lang, self.models["en"])

        try:
            return spacy.load(model_name)
        except OSError:
            raise ImportError(f"spaCy model '{model_name}' not found. Install it with 'python -m spacy download {model_name}'.")

    def parse_intent(self, text: str) -> IntentScoreResponse:
        doc = self._nlp(text)

        entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
        pos_tags = [
            {
                "text": token.text,
                "pos": token.pos_,
                "uri": str(self._resolve_olia_token(token)),
            }
            for token in doc
        ]
        dependencies = [
            {
                "text": token.text,
                "dep": token.dep_,
                "head": token.head.text,
                "uri": str(self._resolve_olia_token(token)),
            }
            for token in doc
        ]
        roots = [
            {
                "text": token.text,
                "pos": token.pos_,
                "lemma": token.lemma_,
                "uri": str(self._resolve_olia_token(token)),
            }
            for token in doc
            if token.dep_ == "ROOT"
        ]

        score = 0.0
        if entities:
            score += 0.5
        if len(doc) > 3:
            score += 0.3
        score += min(0.2, len(doc) * 0.02)

        return IntentScoreResponse(
            text=text,
            entities=entities,
            pos_tags=pos_tags,
            dependencies=dependencies,
            roots=roots,
            score=round(score, 2),
        )

    def _resolve_olia_token(self, token: Token) -> str:
        """
        Iterates through the spaCy token and returns the corresponding URI from the OLiA ontology.
        """
        pos = token.pos_
        # Extract whether the token has the interrogative property in its morphology
        is_interrogative = "PronType=Int" in token.morph
        
        # 1. Try specific match (e.g., Pronoun + Interrogative)
        if is_interrogative and (pos, "PronType=Int") in self.MAPPER_OLIA:
            return self.MAPPER_OLIA[(pos, "PronType=Int")]
        
        # 2. If not interrogative, use base class (e.g., just NOUN, just VERB)
        return self.MAPPER_OLIA.get((pos, None), OLIA["LinguisticSign"])