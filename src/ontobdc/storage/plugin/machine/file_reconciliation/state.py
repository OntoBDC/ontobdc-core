from typing import Any, Dict

from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationProcessStatePort,
)


class FileReconciliationProcessState(FileReconciliationProcessStatePort):
    """
    The states the reconciliation of the files of a container goes through, from the request to
    knowing which files its RO-Crate states are not there, and where a file of the same name is, and
    recording what the files are now in the history the crate keeps.
    """

    UNDEFINED = "__undefined__"
    MISSING_FILES_LISTED = "__missing_files_listed__"
    SAME_NAME_FILES_FOUND = "__same_name_files_found__"
    MOVED_FILES_RELOCATED = "__moved_files_relocated__"
    SAME_NAME_AND_SIZE_FILES_RELOCATED = "__same_name_and_size_files_relocated__"
    ORPHAN_POINTERS_RECORDED = "__orphan_pointers_recorded__"
    CURRENT_STATE_RECORDED = "__current_state_recorded__"
    FILE_IDENTIFIERS_REPLACED = "__file_identifiers_replaced__"
    DATASET_HISTORY_RECORDED = "__dataset_history_recorded__"

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
    def get_state(state: str) -> "FileReconciliationProcessState":
        return getattr(FileReconciliationProcessState, state.upper())

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
