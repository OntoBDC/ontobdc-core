from typing import Any, Dict

from ontobdc.context.plugin.machine.dictionary_inspection.port import (
    DictionaryInspectionProcessStatePort,
)


class DictionaryInspectionProcessState(DictionaryInspectionProcessStatePort):
    """States of the generic dictionary inspection process."""

    UNDEFINED = "__undefined__"
    TEXT_NORMALIZED = "__text_normalized__"
    TEXT_LANGUAGE_IDENTIFIED = "__text_language_identified__"
    TEXT_LEMMATIZED = "__text_lemmatized__"
    ONTOLOGY_TERM_RESOLVED = "__ontology_term_resolved__"
    KIND_REPRESENTATION_RESOLVED = "__kind_representation_resolved__"
    MARKDOWN_RENDERED = "__markdown_rendered__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels: Dict[str, str] = self._normalize_presentation_metadata(label)
        self._descriptions: Dict[str, str] = self._normalize_presentation_metadata(
            description
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
    def get_state(state: str) -> "DictionaryInspectionProcessState":
        return getattr(DictionaryInspectionProcessState, state.upper())

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
