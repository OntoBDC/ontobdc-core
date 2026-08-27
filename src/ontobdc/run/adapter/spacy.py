from typing import Any, Dict, List, Optional, Tuple

from rdflib import Namespace

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OLIA: Optional[Namespace] = _ontology_adapter.get_ontology_namespace_by_prefix("olia")


class SpacyIntentModelResolver:
    """Parse a canonical intent string with spaCy: POS tags, entities,
    dependencies, and the root token(s), each token also carrying a best-
    effort OLiA ontology URI (http://purl.org/olia/olia.owl#...).

    Only the small (``_sm``) spaCy models are used here -- no word vectors,
    smaller download, but real POS/dependency/entity output all the same.
    """

    _MODELS: Dict[str, str] = {
        "en": "en_core_web_sm",
        "pt": "pt_core_news_sm",
        "pt-br": "pt_core_news_sm",
        "pt-pt": "pt_core_news_sm",
    }

    # (part-of-speech, interrogative?) -> OLiA class. Falls back to a base
    # part-of-speech class, then to the generic olia:LinguisticSign.
    _MAPPER_OLIA: Dict[Tuple[str, Optional[str]], Any] = None

    def __init__(self, language: str) -> None:
        self._language: str = language
        self._nlp: Any = self._load_model(language)
        if SpacyIntentModelResolver._MAPPER_OLIA is None:
            SpacyIntentModelResolver._MAPPER_OLIA = self._build_olia_mapper()

    def _load_model(self, language: str) -> Any:
        import spacy

        model_name: str = self._MODELS.get(
            str(language or "").strip().lower(), self._MODELS["en"]
        )
        try:
            return spacy.load(model_name)
        except OSError as error:
            raise ImportError(
                f"spaCy model '{model_name}' is not installed. Install it "
                f"with 'python -m spacy download {model_name}'."
            ) from error

    def _build_olia_mapper(self) -> Dict[Tuple[str, Optional[str]], Any]:
        if OLIA is None:
            return {}
        return {
            ("PRON", "PronType=Int"): OLIA["InterrogativePronoun"],
            ("DET", "PronType=Int"): OLIA["InterrogativePronoun"],
            ("ADV", "PronType=Int"): OLIA["InterrogativeAdverb"],
            ("NOUN", None): OLIA["Noun"],
            ("VERB", None): OLIA["Verb"],
            ("PRON", None): OLIA["Pronoun"],
            ("ADV", None): OLIA["Adverb"],
            ("PUNCT", None): OLIA["Punctuation"],
        }

    def parse(self, text: str) -> Dict[str, Any]:
        doc: Any = self._nlp(text)

        entities: List[Dict[str, Any]] = [
            {"text": entity.text, "label": entity.label_} for entity in doc.ents
        ]
        pos_tags: List[Dict[str, Any]] = [
            {"text": token.text, "pos": token.pos_, "uri": self._olia_uri(token)}
            for token in doc
        ]
        dependencies: List[Dict[str, Any]] = [
            {
                "text": token.text,
                "dep": token.dep_,
                "head": token.head.text,
                "uri": self._olia_uri(token),
            }
            for token in doc
        ]
        roots: List[Dict[str, Any]] = [
            {
                "text": token.text,
                "pos": token.pos_,
                "lemma": token.lemma_,
                "uri": self._olia_uri(token),
            }
            for token in doc
            if token.dep_ == "ROOT"
        ]

        score: float = 0.0
        if entities:
            score += 0.5
        if len(doc) > 3:
            score += 0.3
        score += min(0.2, len(doc) * 0.02)

        return {
            "text": text,
            "entities": entities,
            "pos_tags": pos_tags,
            "dependencies": dependencies,
            "roots": roots,
            "score": round(score, 2),
        }

    def _olia_uri(self, token: Any) -> Optional[str]:
        mapper: Dict[Tuple[str, Optional[str]], Any] = self._MAPPER_OLIA or {}
        if not mapper:
            return None

        part_of_speech: str = token.pos_
        is_interrogative: bool = "PronType=Int" in token.morph

        if is_interrogative and (part_of_speech, "PronType=Int") in mapper:
            return str(mapper[(part_of_speech, "PronType=Int")])

        resolved: Any = mapper.get((part_of_speech, None))
        if resolved is not None:
            return str(resolved)

        return str(OLIA["LinguisticSign"]) if OLIA is not None else None
