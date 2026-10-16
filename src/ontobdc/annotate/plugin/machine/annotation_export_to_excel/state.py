from typing import Any, Dict

from ontobdc.annotate.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelProcessStatePort,
)


class AnnotationExportToExcelProcessState(AnnotationExportToExcelProcessStatePort):
    """
    The states the export of the annotations of one type goes through, from
    the request to the workbook the person receives.
    """

    UNDEFINED = "__undefined__"
    EXPORT_SCOPE_IDENTIFIED = "__export_scope_identified__"
    ANNOTATIONS_COLLECTED = "__annotations_collected__"
    PHOTOS_COLLECTED = "__photos_collected__"
    PHOTOS_DOWNSAMPLED = "__photos_downsampled__"
    WORKBOOK_BUILT = "__workbook_built__"
    WORKBOOK_SAVED = "__workbook_saved__"

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
    def get_state(state: str) -> "AnnotationExportToExcelProcessState":
        return getattr(AnnotationExportToExcelProcessState, state.upper())

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
