from typing import Any, Dict

from ontobdc.cli.plugin.machine.init_addon.port import CliInitAddonProcessStatePort


class CliInitAddonProcessState(CliInitAddonProcessStatePort):
    """
    The states the addition of an addon goes through: the folder of the addon is located, from the folder or the address
    it was given as, and the addon is added. Labels and descriptions come from the statechart that declares them.
    """

    UNDEFINED = "__undefined__"
    ADDON_LOCATED = "__addon_located__"
    ADDON_ADDED = "__addon_added__"

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
    def get_state(state: str) -> "CliInitAddonProcessState":
        return getattr(CliInitAddonProcessState, state.upper())

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
