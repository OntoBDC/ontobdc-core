import re
import textwrap
from dataclasses import dataclass, field
from typing import ClassVar, List, Optional, Pattern, Tuple

from ontobdc.view.domain.port.widget import Widget


@dataclass
class TextWidget(Widget):
    """Heading and/or markdown-lite body text, wrapped to the granted width."""

    heading: str = ""
    body: str = ""

    _HEADING_PATTERN: ClassVar[Pattern[str]] = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
    _BULLET_PATTERN: ClassVar[Pattern[str]] = re.compile(r"^(\s*)[-*+]\s+(.*)$")
    _BOLD_PATTERN: ClassVar[Pattern[str]] = re.compile(r"\*\*(.+?)\*\*")
    _INLINE_CODE_PATTERN: ClassVar[Pattern[str]] = re.compile(r"`([^`]+)`")

    def render(self, available_columns: int) -> List[str]:
        width: int = max(available_columns, 1)
        lines: List[str] = []

        if self.heading.strip():
            lines.append(self.heading.strip())
            lines.append("")

        if self.body.strip():
            lines.extend(self._render_markdown_body(self.body, width))

        return self._collapse_blank_lines(lines)

    def _render_markdown_body(self, body: str, width: int) -> List[str]:
        lines: List[str] = []
        paragraph_buffer: List[str] = []
        code_block_lines: List[str] = []
        inside_code_block: bool = False

        def flush_paragraph() -> None:
            if not paragraph_buffer:
                return

            paragraph_text: str = " ".join(line.strip() for line in paragraph_buffer).strip()
            paragraph_buffer.clear()
            if paragraph_text:
                lines.extend(self._wrap_paragraph(paragraph_text, width))

        def flush_code_block() -> None:
            lines.extend(code_block_lines)
            code_block_lines.clear()

        for raw_line in body.splitlines():
            stripped_line: str = raw_line.strip()

            if stripped_line.startswith("```"):
                flush_paragraph()
                if inside_code_block:
                    flush_code_block()
                inside_code_block = not inside_code_block
                continue

            if inside_code_block:
                code_block_lines.append(raw_line.rstrip())
                continue

            if not stripped_line:
                flush_paragraph()
                lines.append("")
                continue

            heading_match = self._HEADING_PATTERN.match(raw_line)
            if heading_match is not None:
                flush_paragraph()
                lines.append(self._strip_inline_markdown(heading_match.group(2).strip()))
                lines.append("")
                continue

            bullet_match = self._BULLET_PATTERN.match(raw_line)
            if bullet_match is not None:
                flush_paragraph()
                indent_level: int = len(bullet_match.group(1)) // 2
                bullet_text: str = self._strip_inline_markdown(bullet_match.group(2).strip())
                lines.append(f"{'  ' * indent_level}• {bullet_text}")
                continue

            paragraph_buffer.append(raw_line)

        flush_paragraph()
        if inside_code_block:
            flush_code_block()

        return lines

    def _wrap_paragraph(self, text: str, width: int) -> List[str]:
        normalized_text: str = self._strip_inline_markdown(text)
        return textwrap.wrap(normalized_text, width=width, break_long_words=False, break_on_hyphens=False) or [""]

    def _strip_inline_markdown(self, text: str) -> str:
        normalized_text: str = self._BOLD_PATTERN.sub(r"\1", text)
        normalized_text = self._INLINE_CODE_PATTERN.sub(r"\1", normalized_text)
        return normalized_text.strip()

    @staticmethod
    def _collapse_blank_lines(lines: List[str]) -> List[str]:
        collapsed_lines: List[str] = []
        previous_was_blank: bool = False

        for line in lines:
            is_blank: bool = line == ""
            if is_blank and previous_was_blank:
                continue

            collapsed_lines.append(line)
            previous_was_blank = is_blank

        while collapsed_lines and collapsed_lines[-1] == "":
            collapsed_lines.pop()

        return collapsed_lines


@dataclass
class KeyValueWidget:
    """A flat label/value record (rendered as a 2-column pipe table by the terminal renderer)."""

    pairs: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class TableWidget:
    """A rectangular grid of scalar cells (rendered as a pipe-markdown table by the terminal renderer).

    This widget no longer contains its own layout logic; its rendered form is
    produced by the central terminal surface renderer so headers, alignment,
    truncation, colouring and grid drawing all use the same code paths as
    inline markdown tables.
    """

    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class GridWidget:
    """A drawn Tile grid metadata payload: ``columns`` x ``rows`` cells of
    ``slot_width`` x ``slot_height``.  The textual drawing previously
    implemented in ``render`` is now provided by dedicated surface
    components; this dataclass only carries the structural data.
    """

    columns: int = 1
    rows: int = 1
    slot_width: int = 20
    slot_height: int = 5
    operation_enabled: bool = False
    pinned_enabled: bool = False


@dataclass
class CodeBlockWidget:
    """Pre-formatted text (e.g. JSON) printed verbatim inside a fenced code block."""

    text: str = ""


@dataclass
class ErrorWidget:
    """An error message with an optional traceback.

    Rendered as a fenced code block by the central terminal renderer so both
    the message and any traceback share the same mono-font formatting.
    """

    message: str = ""
    traceback: Optional[str] = None
