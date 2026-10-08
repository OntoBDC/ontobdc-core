from typing import Any, Dict

from ontobdc.cli.plugin.machine.init.port import CliInitProcessStatePort


class CliInitProcessState(CliInitProcessStatePort):
    """
    The states a project goes through, from a directory with nothing in it to
    a project OntoBDC can work in. Labels and descriptions come from the
    statechart that declares them.
    """

    UNDEFINED = "__undefined__"
    ONTOBDC_DIRECTORY_READY = "__ontobdc_directory_ready__"
    ENGINE_READY = "__engine_ready__"
    STORAGE_INDEX_HEALTHY = "__storage_index_healthy__"
    EXECUTION_CONTEXT_HEALTHY = "__execution_context_healthy__"
    CONFIG_ADAPTER_READY = "__config_adapter_ready__"
    BRAND_READY = "__brand_ready__"

    def __init__(self, _: str) -> None:
        self._labels: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def bind_presentation_metadata(
        self,
        label: Any = None,
        description: Any = None,
    ) -> None:
        self._labels = self._normalize(label)
        self._descriptions = self._normalize(description)

    def label(self, lang: str = "en") -> str:
        return self._localized(self._labels, lang, self.value)

    def description(self, lang: str = "en") -> str:
        return self._localized(self._descriptions, lang, "")

    @staticmethod
    def get_state(state: str) -> "CliInitProcessState":
        return getattr(CliInitProcessState, state.upper())

    @staticmethod
    def _normalize(value: Any) -> Dict[str, str]:
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
    def _localized(values: Dict[str, str], lang: str, default: str) -> str:
        normalized: str = lang.strip().lower().replace("_", "-")
        return values.get(normalized, values.get("en", default))
