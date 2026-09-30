from __future__ import annotations

from typing import Any, Dict

from ontobdc.storage.plugin.machine.open_file.port import OpenFileProcessStatePort


class OpenFileProcessState(OpenFileProcessStatePort):
    UNDEFINED = "__undefined__"
    FILE_METADATA_EXTRACTED = "__file_metadata_extracted__"
    FILE_OPENING_STRATEGY_FOUND = "__file_opening_strategy_found__"

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            getattr(self, "_labels", {}),
            lang,
            self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            getattr(self, "_descriptions", {}),
            lang,
            "",
        )

    @staticmethod
    def get_state(state: str) -> "OpenFileProcessState":
        return getattr(OpenFileProcessState, state.upper())

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
        normalized_lang = lang.strip().lower().replace("_", "-")
        return values.get(normalized_lang, values.get("en", default))
