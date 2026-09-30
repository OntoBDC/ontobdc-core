from typing import Any, Dict

from ontobdc.context.plugin.machine.file_meaning_suggestion.port import (
    FileMeaningSuggestionProcessStatePort,
)


class FileMeaningSuggestionProcessState(FileMeaningSuggestionProcessStatePort):
    """
    Enum representing the states of the file meaning suggestion process.
    """

    UNDEFINED = "__undefined__"
    PATH_NORMALIZED = "__path_normalized__"
    PATH_LANGUAGE_IDENTIFIED = "__path_language_identified__"
    FILE_METADATA_EXTRACTED = "__file_metadata_extracted__"
    PATH_LEMMATIZED = "__path_lemmatized__"
    TOKEN_STATISTICS_COMPUTED = "__token_statistics_computed__"
    CHUNK_CANDIDATES_GENERATED = "__chunk_candidates_generated__"
    CHUNKS_EXTRACTED = "__chunks_extracted__"
    ONTOLOGY_TERMS_MATCHED = "__ontology_terms_matched__"
    CATEGORY_CANDIDATES_FOUND = "__category_candidates_found__"
    FUZZY_CATEGORY_CANDIDATES_ENRICHED = "__fuzzy_category_candidates_enriched__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels: Dict[str, str] = self._normalize_presentation_metadata(
            label
        )
        self._descriptions: Dict[str, str] = (
            self._normalize_presentation_metadata(description)
        )

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_labels", {}),
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=getattr(self, "_descriptions", {}),
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "FileMeaningSuggestionProcessState":
        return getattr(FileMeaningSuggestionProcessState, state.upper())

    @staticmethod
    def _normalize_presentation_metadata(value: Any) -> Dict[str, str]:
        if isinstance(value, str):
            return {"en": value}
        if not isinstance(value, dict):
            return {}

        return {
            str(language).strip().lower().replace("_", "-"): str(text)
            for language, text in value.items()
            if str(language).strip() and text is not None
        }

    @staticmethod
    def _localized_presentation_metadata(
        values: Dict[str, str],
        lang: str,
        default: str,
    ) -> str:
        normalized_lang: str = lang.strip().lower().replace("_", "-")

        return values.get(normalized_lang, values.get("en", default))
