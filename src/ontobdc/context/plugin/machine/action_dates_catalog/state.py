from typing import Any, Dict

from ontobdc.context.plugin.machine.action_dates_catalog.port import ActionDatesCatalogProcessStatePort


class ActionDatesCatalogProcessState(ActionDatesCatalogProcessStatePort):
    """
    The states the cataloging of the dates of the actions in a container passes through.

    A state is only valid while it makes sense to keep going. A container with no RO-Crate is not a state of
    the cataloging: it is an exception, and ends the command.
    """

    UNDEFINED = "__undefined__"
    DAYS_CATALOGED = "__days_cataloged__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize_presentation_metadata(label)
        self._descriptions = self._normalize_presentation_metadata(description)

    def label(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._labels,
            lang=lang,
            default=self.value,
        )

    def description(self, lang: str = "en") -> str:
        return self._localized_presentation_metadata(
            values=self._descriptions,
            lang=lang,
            default="",
        )

    @staticmethod
    def get_state(state: str) -> "ActionDatesCatalogProcessState":
        return getattr(ActionDatesCatalogProcessState, state.upper())

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
