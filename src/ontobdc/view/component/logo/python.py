import shutil
from importlib import metadata
from typing import List, Optional, TextIO, Tuple

from pyfiglet import Figlet

from ontobdc.shared.adapter.terminal_color import (
    ANSI_ESCAPE_REGEX,
    RESET,
    rgb_fg,
    rgb_fg_bold,
)


class LogoComponent:
    """Terminal representation of the OntoBDC logo component."""

    PRIMARY_TEXT = "Onto"
    ACCENT_TEXT = "BDC"
    TEXT_VALUE = PRIMARY_TEXT + ACCENT_TEXT
    TEXT_FONT = "standard"
    PRIMARY_COLOR = (255, 255, 255)
    BANNER_COLOR = (0, 180, 216)
    LEGACY_BANNER_COLOR = (25, 70, 109)
    VERSION_GAP = "  "
    COMPACT_MARKER = ">_ "

    def __init__(
        self,
        *,
        version: Optional[str] = None,
        center: bool = True,
        color: bool = True,
    ) -> None:
        self._version = version
        self._center = center
        self._color = color

    def render(self, *, terminal_width: Optional[int] = None) -> str:
        figlet = Figlet(font=self.TEXT_FONT)
        # "Onto" and "BDC" are rendered separately (instead of slicing the
        # combined "OntoBDC" render) so each half can carry its own brand
        # color without guessing where one glyph ends and the next begins.
        primary_lines: List[str] = (
            figlet.renderText(self.PRIMARY_TEXT).rstrip("\n").splitlines()
        )
        accent_lines: List[str] = (
            figlet.renderText(self.ACCENT_TEXT).rstrip("\n").splitlines()
        )
        combined_lines: List[str] = [
            primary + accent for primary, accent in zip(primary_lines, accent_lines)
        ]
        version_label = self._version_label()

        if combined_lines and version_label:
            last_index = self._last_non_empty_line_index(combined_lines)
            accent_lines[last_index] = (
                f"{accent_lines[last_index]}{self.VERSION_GAP}{version_label}"
            )

        if self._color:
            logo_lines = [
                f"{rgb_fg(*self.PRIMARY_COLOR)}{primary}{RESET}"
                f"{rgb_fg_bold(*self.BANNER_COLOR)}{accent}{RESET}"
                if (primary + accent).strip()
                else ""
                for primary, accent in zip(primary_lines, accent_lines)
            ]
        else:
            logo_lines = [
                primary + accent for primary, accent in zip(primary_lines, accent_lines)
            ]

        banner = "\n".join(logo_lines)
        if not self._center:
            return banner

        return self._center_banner(banner, terminal_width=terminal_width)

    def render_compact(self) -> str:
        """One-line default representation: a marker plus the plain name.

        This is the default Tile size for the logo. `render()` is the large
        ANSI-art variant, reserved for callers that explicitly ask for it.
        """
        if not self._color:
            return f"{self.COMPACT_MARKER}{self.TEXT_VALUE}"

        primary = f"{rgb_fg(*self.PRIMARY_COLOR)}{self.PRIMARY_TEXT}{RESET}"
        accent = f"{rgb_fg_bold(*self.BANNER_COLOR)}{self.ACCENT_TEXT}{RESET}"
        return f"{self.COMPACT_MARKER}{primary}{accent}"

    def print(
        self,
        *,
        file: Optional[TextIO] = None,
        terminal_width: Optional[int] = None,
    ) -> None:
        print(self.render(terminal_width=terminal_width), file=file)

    def rgb(self) -> Tuple[int, int, int]:
        return self.BANNER_COLOR

    def width(self, *, terminal_width: Optional[int] = None) -> int:
        lines = self.render(terminal_width=terminal_width).splitlines()
        return max((self._visible_length(line) for line in lines), default=0)

    def _last_non_empty_line_index(self, lines: List[str]) -> int:
        for line_index in range(len(lines) - 1, -1, -1):
            if lines[line_index].strip():
                return line_index
        return max(len(lines) - 1, 0)

    def _center_banner(
        self,
        banner: str,
        *,
        terminal_width: Optional[int] = None,
    ) -> str:
        banner_lines = banner.splitlines()
        banner_width = max(
            (self._visible_length(line) for line in banner_lines),
            default=0,
        )
        width = terminal_width
        if width is None:
            width = shutil.get_terminal_size(
                fallback=(banner_width, 40)
            ).columns
        left_padding = max((width - banner_width) // 2, 0)
        padding = " " * left_padding
        return "\n".join(
            f"{padding}{line}" if line else ""
            for line in banner_lines
        )

    def _visible_length(self, value: str) -> int:
        return len(ANSI_ESCAPE_REGEX.sub("", value))

    def _version_label(self) -> str:
        version = self._version
        if version is None:
            try:
                version = metadata.version("ontobdc")
            except metadata.PackageNotFoundError:
                version = None

        if not version:
            return ""
        return version if str(version).startswith("v") else f"v{version}"
