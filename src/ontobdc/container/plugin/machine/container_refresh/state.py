from typing import Any, Dict

from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshProcessStatePort,
)


class ContainerRefreshProcessState(ContainerRefreshProcessStatePort):
    """
    Enum representing the possible states of the storage container refresh process.
    """

    UNDEFINED = "__undefined__"
    CONTAINER_INVALID = "__container_invalid__"
    CONTAINER_HEALTHY = "__container_healthy__"
    CONTAINER_DATASETS_HEALTHY = "__container_datasets_healthy__"
    CONTAINER_CLEANED = "__container_cleaned__"
    CONTAINER_DATAPACKAGE_UPDATED = "__container_datapackage_updated__"
    CONTAINER_RO_CRATE_UPDATED = "__container_ro_crate_updated__"
    CONTAINER_UPDATED = "__container_updated__"

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
    def get_state(state: str) -> "ContainerRefreshProcessState":
        return getattr(ContainerRefreshProcessState, state.upper())

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
        if normalized_lang in values:
            return values[normalized_lang]
        if "en" in values:
            return values["en"]

        return default
