import re
import shutil
from typing import ClassVar, Dict, List, Pattern

from ontobdc.view.domain.port.layout import (
    MessageBoxLayoutData,
    MessageBoxLayoutRendererPort,
)


class RichMessageBoxLayout(MessageBoxLayoutRendererPort):
    """Render command responses as ANSI-colored terminal message boxes."""

    BOLD: ClassVar[str] = "\033[1m"
    RESET: ClassVar[str] = "\033[0m"
    CYAN: ClassVar[str] = "\033[36m"
    GRAY: ClassVar[str] = "\033[90m"
    WHITE: ClassVar[str] = "\033[37m"
    YELLOW: ClassVar[str] = "\033[1;33m"
    GREEN: ClassVar[str] = "\033[32m"
    RED: ClassVar[str] = "\033[31m"
    BLUE: ClassVar[str] = "\033[34m"
    ANSI_ESCAPE_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"\x1b\[[0-9;]*m"
    )
    MARKDOWN_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"(^\s{0,3}#{1,6}\s)|(^\s*[-*+]\s)|(\*\*[^*]+\*\*)|"
        r"(^```)|(`[^`]+`)",
        re.MULTILINE,
    )
    HEADING_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"^\s{0,3}(#{1,6})\s+(.*)$"
    )
    BULLET_PATTERN: ClassVar[Pattern[str]] = re.compile(
        r"^(\s*)[-*+]\s+(.*)$"
    )
    BOLD_PATTERN: ClassVar[Pattern[str]] = re.compile(r"\*\*(.+?)\*\*")
    INLINE_CODE_PATTERN: ClassVar[Pattern[str]] = re.compile(r"`([^`]+)`")
    MIN_TERMINAL_WIDTH: ClassVar[int] = 20
    DEFAULT_TERMINAL_WIDTH: ClassVar[int] = 80
    COLOR_MAP: ClassVar[Dict[str, str]] = {
        "RED": RED,
        "GREEN": GREEN,
        "YELLOW": YELLOW,
        "CYAN": CYAN,
        "BLUE": BLUE,
        "WHITE": WHITE,
        "GRAY": GRAY,
        "INFO": BLUE,
    }

    def render(self, layout_data: MessageBoxLayoutData) -> str:
        color: str = layout_data.color
        title_type: str = layout_data.title_type
        title_text: str = layout_data.title
        message_text: str = layout_data.content
        subtitle_text: str = layout_data.subtitle
        footer_text: str = layout_data.footer

        terminal_columns: int = self._resolve_terminal_width()
        inner_width: int = terminal_columns - 2
        horizontal_line: str = "─" * inner_width
        border_color: str = self._resolve_color(color)
        lines: List[str] = []

        lines.append(f"{border_color}╭{horizontal_line}╮{self.RESET}")
        lines.append(
            self._frame_line(
                self._build_title_content(
                    color=color,
                    title_type=title_type,
                    title_text=title_text,
                ),
                inner_width,
                border_color,
            )
        )
        lines.append(self._empty_line(inner_width, border_color))

        if subtitle_text:
            subtitle_line: str = (
                f"{self.GRAY}{subtitle_text}{self.RESET}"
            )
            lines.append(
                self._frame_line(
                    subtitle_line,
                    inner_width,
                    border_color,
                )
            )
            lines.append(self._empty_line(inner_width, border_color))

        lines.extend(
            self._build_message_lines(
                message_text,
                inner_width,
                border_color,
            )
        )

        if footer_text:
            lines.append(self._empty_line(inner_width, border_color))
            lines.append(
                self._build_footer_line(
                    footer_text,
                    inner_width,
                    border_color,
                )
            )
        else:
            lines.append(
                f"{border_color}╰{horizontal_line}╯{self.RESET}"
            )

        return "\n".join(lines)

    def _build_title_content(
        self,
        color: str,
        title_type: str,
        title_text: str,
    ) -> str:
        title_type_color: str = (
            self.BLUE
            if title_type == "OntoBDC"
            else self._resolve_color(color)
        )
        title_head: str = (
            f" >_ {self.BOLD}{title_type_color}"
            f"{title_type}{self.RESET}"
        )

        if not title_text:
            return title_head

        return f"{title_head} {title_text}"

    def _build_message_lines(
        self,
        message_text: str,
        inner_width: int,
        border_color: str,
    ) -> List[str]:
        raw_lines: List[str] = (
            self._resolve_message_lines(message_text, inner_width) or [""]
        )
        framed_lines: List[str] = []

        for raw_line in raw_lines:
            wrapped_chunks: List[str] = self._wrap_visible_line(
                raw_line,
                inner_width,
            )

            for chunk in wrapped_chunks:
                gray_chunk: str = f"{self.GRAY} {chunk}{self.RESET}"
                framed_lines.append(
                    self._frame_line(
                        gray_chunk,
                        inner_width,
                        border_color,
                    )
                )

        return framed_lines

    def _resolve_message_lines(
        self,
        message_text: str,
        inner_width: int,
    ) -> List[str]:
        _ = inner_width
        if not self._looks_like_markdown(message_text):
            return self._collapse_empty_lines(message_text.splitlines())

        return self._render_markdown_lines(message_text)

    def _looks_like_markdown(self, message_text: str) -> bool:
        return bool(self.MARKDOWN_PATTERN.search(message_text))

    def _render_markdown_lines(self, message_text: str) -> List[str]:
        lines: List[str] = []

        for raw_line in message_text.splitlines():
            stripped_line: str = raw_line.strip()
            if stripped_line == "":
                lines.append("")
                continue

            heading_match = self.HEADING_PATTERN.match(raw_line)
            if heading_match is not None:
                heading_level: int = len(heading_match.group(1))
                heading_text: str = self._strip_inline_markdown(
                    heading_match.group(2).strip()
                )
                lines.extend(
                    self._format_heading_line(
                        heading_text,
                        heading_level,
                    )
                )
                continue

            bullet_match = self.BULLET_PATTERN.match(raw_line)
            if bullet_match is not None:
                indent_width: int = len(bullet_match.group(1))
                indent_level: int = indent_width // 2
                bullet_text: str = self._strip_inline_markdown(
                    bullet_match.group(2).strip()
                )
                lines.append(f"{'  ' * indent_level}• {bullet_text}")
                continue

            lines.append(self._strip_inline_markdown(stripped_line))

        return self._collapse_empty_lines(lines)

    def _format_heading_line(
        self,
        heading_text: str,
        heading_level: int,
    ) -> List[str]:
        if heading_level <= 2:
            return [heading_text, ""]

        if heading_level == 3:
            return [f"{heading_text}:"]

        return [f"  {heading_text}:"]

    def _strip_inline_markdown(self, content: str) -> str:
        normalized_content: str = self.BOLD_PATTERN.sub(r"\1", content)
        normalized_content = self.INLINE_CODE_PATTERN.sub(
            r"\1",
            normalized_content,
        )
        return normalized_content.strip()

    def _collapse_empty_lines(self, lines: List[str]) -> List[str]:
        collapsed_lines: List[str] = []
        previous_line_was_empty: bool = False

        for line in lines:
            is_empty_line: bool = line.strip() == ""
            if is_empty_line and previous_line_was_empty:
                continue

            collapsed_lines.append(line)
            previous_line_was_empty = is_empty_line

        return collapsed_lines

    def _build_footer_line(
        self,
        footer_text: str,
        inner_width: int,
        border_color: str,
    ) -> str:
        footer_visible_length: int = self._visible_length(footer_text)
        remaining_width: int = inner_width - footer_visible_length - 3

        if remaining_width < 0:
            remaining_width = 0

        left_line: str = "─"
        right_line: str = "─" * remaining_width
        return (
            f"{border_color}╰{left_line} {footer_text} "
            f"{right_line}╯{self.RESET}"
        )

    def _frame_line(
        self,
        content: str,
        inner_width: int,
        border_color: str,
    ) -> str:
        padded_content: str = self._pad_visible_content(
            content,
            inner_width,
        )
        return (
            f"{border_color}│{self.RESET}{padded_content}"
            f"{border_color}│{self.RESET}"
        )

    def _empty_line(
        self,
        inner_width: int,
        border_color: str,
    ) -> str:
        empty_content: str = " " * inner_width
        return (
            f"{border_color}│{self.RESET}{empty_content}"
            f"{border_color}│{self.RESET}"
        )

    def _pad_visible_content(
        self,
        content: str,
        inner_width: int,
    ) -> str:
        visible_length: int = self._visible_length(content)
        padding_length: int = inner_width - visible_length

        if padding_length < 0:
            padding_length = 0

        padding: str = " " * padding_length
        return f"{content}{padding}"

    def _wrap_visible_line(
        self,
        content: str,
        inner_width: int,
    ) -> List[str]:
        clean_content: str = self._strip_ansi(content)
        wrapped_chunks: List[str] = []
        start_index: int = 0

        if clean_content == "":
            return [""]

        if len(clean_content) <= inner_width:
            return [content]

        while start_index < len(clean_content):
            end_index: int = start_index + inner_width
            wrapped_chunks.append(clean_content[start_index:end_index])
            start_index = end_index

        return wrapped_chunks

    def _resolve_terminal_width(self) -> int:
        terminal_size = shutil.get_terminal_size(
            fallback=(self.DEFAULT_TERMINAL_WIDTH, 24)
        )
        columns: int = terminal_size.columns

        if columns < self.MIN_TERMINAL_WIDTH:
            return self.DEFAULT_TERMINAL_WIDTH

        return columns

    def _resolve_color(self, color: str) -> str:
        return self.COLOR_MAP.get(color.upper(), color)

    def _strip_ansi(self, content: str) -> str:
        return self.ANSI_ESCAPE_PATTERN.sub("", content)

    def _visible_length(self, content: str) -> int:
        return len(self._strip_ansi(content))
