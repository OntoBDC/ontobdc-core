from pathlib import Path
from typing import List
from xml.etree import ElementTree

from ontobdc.shared.domain.model.draw import (
    DrawSource,
    DrawSourceKind,
)
from ontobdc.shared.domain.port.draw import DrawSourceStrategyPort


class SvgDrawSourceStrategy(DrawSourceStrategyPort):
    """Recognize SVG sources from their XML root element."""

    priority: int = 200

    def accepts(self, source_path: Path) -> bool:
        try:
            root: ElementTree.Element = ElementTree.fromstring(
                source_path.read_bytes()
            )
        except (OSError, ElementTree.ParseError):
            return False
        return root.tag.rsplit("}", 1)[-1].lower() == "svg"

    def load(self, source_path: Path) -> DrawSource:
        content: bytes = source_path.read_bytes()
        root: ElementTree.Element = ElementTree.fromstring(content)
        normalized_content: bytes = ElementTree.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
        )
        view_box: str = root.attrib.get("viewBox", "").strip()
        width: int = self._dimension(root.attrib.get("width"), view_box, 2)
        height: int = self._dimension(root.attrib.get("height"), view_box, 3)
        return DrawSource(
            kind=DrawSourceKind.VECTOR,
            source_format="SVG",
            content_format="SVG",
            content=normalized_content,
            width=width,
            height=height,
        )

    @staticmethod
    def _dimension(
        explicit_value: str | None,
        view_box: str,
        view_box_index: int,
    ) -> int:
        if explicit_value:
            numeric_value: str = "".join(
                character
                for character in explicit_value
                if character.isdigit() or character == "."
            )
            if numeric_value:
                return round(float(numeric_value))

        view_box_values: List[str] = view_box.replace(",", " ").split()
        if len(view_box_values) == 4:
            return round(float(view_box_values[view_box_index]))
        return 0
