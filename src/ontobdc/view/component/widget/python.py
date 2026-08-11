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
class KeyValueWidget(Widget):
    """A flat label/value record, laid out as two aligned columns."""

    pairs: List[Tuple[str, str]] = field(default_factory=list)

    def render(self, available_columns: int) -> List[str]:
        if not self.pairs:
            return []

        label_width: int = min(
            max(len(label) for label, _ in self.pairs),
            max(available_columns - 4, 1),
        )
        value_width: int = max(available_columns - label_width - 2, 1)
        continuation_indent: str = " " * (label_width + 2)

        lines: List[str] = []
        for label, value in self.pairs:
            wrapped_value: List[str] = textwrap.wrap(str(value), width=value_width) or [""]
            lines.append(f"{label.ljust(label_width)}  {wrapped_value[0]}")
            lines.extend(f"{continuation_indent}{extra_line}" for extra_line in wrapped_value[1:])

        return lines


@dataclass
class TableWidget(Widget):
    """A rectangular grid of scalar cells, column widths fit to the granted width."""

    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

    def render(self, available_columns: int) -> List[str]:
        if not self.headers:
            return []

        column_widths: List[int] = self._fit_column_widths(
            self._natural_column_widths(),
            available_columns,
        )

        lines: List[str] = [self._format_row(self.headers, column_widths)]
        lines.extend(self._format_row(row, column_widths) for row in self.rows)
        return lines

    def _natural_column_widths(self) -> List[int]:
        widths: List[int] = [len(header) for header in self.headers]
        for row in self.rows:
            for index, cell in enumerate(row):
                if index < len(widths):
                    widths[index] = max(widths[index], len(cell))

        return [max(width, 1) for width in widths]

    def _fit_column_widths(self, widths: List[int], available_columns: int) -> List[int]:
        gap_width: int = 2 * (len(widths) - 1) if len(widths) > 1 else 0
        overflow: int = sum(widths) + gap_width - max(available_columns, 1)
        if overflow <= 0 or len(widths) <= 1:
            return widths

        fitted_widths: List[int] = list(widths)
        shrinkable_total: int = sum(fitted_widths[1:]) or 1
        for index in range(1, len(fitted_widths)):
            share: int = round(overflow * (fitted_widths[index] / shrinkable_total))
            fitted_widths[index] = max(3, fitted_widths[index] - share)

        return fitted_widths

    def _format_row(self, cells: List[str], column_widths: List[int]) -> str:
        rendered_cells: List[str] = [
            self._truncate(cells[index] if index < len(cells) else "", width).ljust(width)
            for index, width in enumerate(column_widths)
        ]
        return "  ".join(rendered_cells)

    @staticmethod
    def _truncate(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        if width <= 1:
            return text[:width]

        return f"{text[: width - 1]}…"


@dataclass
class GridWidget(Widget):
    """A drawn Tile grid: `columns` x `rows` cells of `slot_width` x `slot_height`.

    Visualizes the PresentationSurface's own grid math (TerminalSurface's
    logical_columns/visible_logical_rows over its slot_width/slot_height)
    instead of just reporting the numbers. Each cell shows two lines: its
    `row,column` coordinate and its `slot_width x slot_height` size — unless
    the slot is only one line tall, in which case the coordinate alone is
    shown.

    `rows` is only the tile-content rows (e.g. TerminalSurface's
    `visible_logical_rows`, which already excludes space reserved for the
    operation/pinned bars). When `operation_enabled`/`pinned_enabled` are
    set, that reserved space is drawn explicitly as a labeled band above
    and/or below the tile grid, at its real `slot_height`, instead of
    silently disappearing from a rows count with nothing shown for it.
    """

    columns: int = 1
    rows: int = 1
    slot_width: int = 20
    slot_height: int = 5
    operation_enabled: bool = False
    pinned_enabled: bool = False

    def render(self, available_columns: int) -> List[str]:
        _ = available_columns
        columns: int = max(self.columns, 1)
        rows: int = max(self.rows, 1)
        slot_width: int = max(self.slot_width, 1)
        slot_height: int = max(self.slot_height, 1)
        total_width: int = len(self._border(columns, slot_width))

        lines: List[str] = []
        if self.operation_enabled:
            lines.extend(self._band("operation", total_width, slot_height))

        lines.extend(self._tile_grid(columns, rows, slot_width, slot_height))

        if self.pinned_enabled:
            lines.extend(self._band("pinned", total_width, slot_height))

        return lines

    def _tile_grid(self, columns: int, rows: int, slot_width: int, slot_height: int) -> List[str]:
        coordinate_line, size_line = self._label_lines(slot_height)
        size_label: str = f"{slot_width}x{slot_height}"

        lines: List[str] = [self._border(columns, slot_width)]
        for row in range(rows):
            for line_index in range(slot_height):
                if line_index == coordinate_line:
                    texts: Optional[List[str]] = [f"{row},{column}" for column in range(columns)]
                elif line_index == size_line:
                    texts = [size_label for _ in range(columns)]
                else:
                    texts = None

                lines.append(self._row_line(texts, columns, slot_width))
            lines.append(self._border(columns, slot_width))

        return lines

    @staticmethod
    def _label_lines(slot_height: int) -> Tuple[int, int]:
        """Two adjacent, roughly centered line indexes for the cell label.

        When there is room for only one line (`slot_height` == 1), both
        indexes collapse to the same line, and only the coordinate — checked
        first in `_tile_grid` — ends up shown.
        """
        coordinate_line: int = max((slot_height - 2) // 2, 0)
        size_line: int = coordinate_line + 1 if slot_height > 1 else coordinate_line
        return coordinate_line, size_line

    @staticmethod
    def _band(label: str, total_width: int, slot_height: int) -> List[str]:
        inner_width: int = max(total_width - 2, 1)
        horizontal: str = "+" + "-" * inner_width + "+"
        label_line: int = max((slot_height - 1) // 2, 0)

        lines: List[str] = [horizontal]
        for line_index in range(slot_height):
            text: str = label if line_index == label_line else ""
            lines.append(f"|{text.center(inner_width)}|")
        lines.append(horizontal)

        return lines

    @staticmethod
    def _border(columns: int, slot_width: int) -> str:
        return "+" + "+".join("-" * slot_width for _ in range(columns)) + "+"

    @staticmethod
    def _row_line(texts: Optional[List[str]], columns: int, slot_width: int) -> str:
        cells: List[str] = [
            texts[column].center(slot_width) if texts else " " * slot_width
            for column in range(columns)
        ]
        return "|" + "|".join(cells) + "|"


@dataclass
class CodeBlockWidget(Widget):
    """Pre-formatted text (e.g. JSON) printed verbatim, without reflow."""

    text: str = ""

    def render(self, available_columns: int) -> List[str]:
        _ = available_columns
        if not self.text:
            return []

        return self.text.splitlines()


@dataclass
class ErrorWidget(Widget):
    """An error message with an optional traceback, printed verbatim."""

    message: str = ""
    traceback: Optional[str] = None

    def render(self, available_columns: int) -> List[str]:
        _ = available_columns
        lines: List[str] = [f"Error: {self.message}" if self.message else "Error"]

        if self.traceback:
            lines.append("")
            lines.append("Traceback:")
            lines.extend(self.traceback.splitlines())

        return lines
