from typing import Any, Dict

from ontobdc.context.plugin.machine.pdf_to_graph.port import (
    PdfToGraphProcessStatePort,
)


class PdfToGraphProcessState(PdfToGraphProcessStatePort):
    """
    Enum representing the states of the PDF-to-knowledge-graph process.
    """

    UNDEFINED = "__undefined__"
    TEXT_READINESS_CHECKED = "__text_readiness_checked__"
    PDF_BLOCKS_EXTRACTED = "__pdf_blocks_extracted__"

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
    def get_state(state: str) -> "PdfToGraphProcessState":
        return getattr(PdfToGraphProcessState, state.upper())

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
