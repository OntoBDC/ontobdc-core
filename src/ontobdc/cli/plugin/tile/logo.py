import shutil
from typing import Any, Dict, List, Optional, TextIO, Tuple
from importlib import metadata

from rdflib import Namespace
from pyfiglet import Figlet

from ontobdc.shared.domain.port.component import (
    ComponentPort,
    TerminalTileRenderable,
)
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.shared.domain.model.component import ComponentMetadata

_VIEW = Namespace("http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#")


class LogoComponent:
    """Terminal representation of the OntoBDC logo component."""

    PRIMARY_TEXT = "Onto"
    ACCENT_TEXT = "BDC"
    TEXT_VALUE = PRIMARY_TEXT + ACCENT_TEXT
    TEXT_FONT = "standard"
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
            # The primary half is left in the terminal's own default
            # foreground rather than a fixed color: a color chosen to read
            # on one background (white for a dark terminal) is invisible
            # on the opposite one, and this component has no way to know
            # which background it is actually being read against.
            logo_lines = [
                f"{primary}"
                f"{TerminalColor.rgb_fg_bold(*self.BANNER_COLOR)}{accent}{TerminalColor.RESET}"
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

        # See render()'s own comment: the primary half stays in the
        # terminal's default foreground so it reads on either a light or
        # a dark background, rather than a fixed color that only reads on
        # one of them.
        accent = (
            f"{TerminalColor.rgb_fg_bold(*self.BANNER_COLOR)}"
            f"{self.ACCENT_TEXT}{TerminalColor.RESET}"
        )
        return f"{self.COMPACT_MARKER}{self.PRIMARY_TEXT}{accent}"

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
        return len(TerminalColor.ANSI_ESCAPE_REGEX.sub("", value))

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


class TerminalLogoTile(ComponentPort, TerminalTileRenderable):
    """Terminal 1x1 default rendering for the :view:`LogoTile` chrome tile.

    Reuses the existing ``LogoComponent.render_compact`` compact marker — the
    small ``>_ OntoBDC`` one-line brand — unchanged. The same
    ``view:LogoTile`` class is matched by both this terminal implementation
    (registered in the core ``ontobdc.view`` component tree) and the
    ``LogoTileComponent`` browser implementation (registered in
    ``ontobdc_view.component.plugin``). Which one runs is decided by the
    renderer (terminal Surface vs. HTML Surface), not by the matching step.
    """

    METADATA = ComponentMetadata(
        id="org.ontobdc.view.component.logo.terminal",
        tag="onto-logo-tile-terminal",
        tile_class=str(_VIEW.LogoTile),
        version="1.0.0",
        name="Logo Tile (Terminal)",
        description="Renders the compact 1x1 terminal brand marker.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "chrome", "terminal", "branding"],
        supported_languages=["en", "pt-BR", "pt-PT", "es"],
        min_columns=1,
        max_columns=8,
        min_rows=1,
        max_rows=3,
    )

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        color: bool = True
        center: bool = False
        if context is not None:
            if "color" in context:
                color = bool(context["color"])
            if "center" in context:
                center = bool(context["center"])
        component = LogoComponent(center=center, color=color)
        return component.render_compact()
