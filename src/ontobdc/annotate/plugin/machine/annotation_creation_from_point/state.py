from typing import Any, Dict

from ontobdc.annotate.plugin.machine.annotation_creation_from_point.port import (
    AnnotationCreationFromPointProcessStatePort,
)


class AnnotationCreationFromPointProcessState(
    AnnotationCreationFromPointProcessStatePort
):
    """
    The states an annotation passes through while it is created from points
    picked on a drawing, starting from the identification of its type.
    """

    UNDEFINED = "__undefined__"
    ANNOTATION_TYPE_IDENTIFIED = "__annotation_type_identified__"
    FILE_METADATA_EXTRACTED = "__file_metadata_extracted__"
    DRAWABLE_DOCUMENTS_LOADED = "__drawable_documents_loaded__"
    DRAWABLE_FILE_VIEWER_OPENED = "__drawable_file_viewer_opened__"
    POINTS_CAPTURED = "__points_captured__"
    ANNOTATION_DETAILS_FILLED = "__annotation_details_filled__"
    ANNOTATIONS_CREATED = "__annotations_created__"

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
    def get_state(state: str) -> "AnnotationCreationFromPointProcessState":
        return getattr(AnnotationCreationFromPointProcessState, state.upper())

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
