import re
from typing import ClassVar, Dict, Optional, Pattern, Tuple


class TerminalColor:
    """
    Single source of truth for the ANSI SGR sequences used in the terminal.

    The values are the historical ones from the CLI logger, so the rendered
    palette stays unchanged.
    """
    RESET: ClassVar[str] = "\033[0m"

    BLACK: ClassVar[str] = "\033[30m"
    RED: ClassVar[str] = "\033[31m"
    GREEN: ClassVar[str] = "\033[32m"
    YELLOW: ClassVar[str] = "\033[33m"
    BLUE: ClassVar[str] = "\033[34m"
    MAGENTA: ClassVar[str] = "\033[35m"
    CYAN: ClassVar[str] = "\033[36m"
    WHITE: ClassVar[str] = "\033[37m"

    BRIGHT_BLACK: ClassVar[str] = "\033[90m"
    BRIGHT_RED: ClassVar[str] = "\033[91m"
    BRIGHT_GREEN: ClassVar[str] = "\033[92m"
    BRIGHT_YELLOW: ClassVar[str] = "\033[93m"
    BRIGHT_BLUE: ClassVar[str] = "\033[94m"
    BRIGHT_MAGENTA: ClassVar[str] = "\033[95m"
    BRIGHT_CYAN: ClassVar[str] = "\033[96m"
    BRIGHT_WHITE: ClassVar[str] = "\033[97m"

    GRAY: ClassVar[str] = BRIGHT_BLACK

    BOLD: ClassVar[str] = "\033[1m"
    DIM: ClassVar[str] = "\033[2m"
    NORMAL_INTENSITY: ClassVar[str] = "\033[22m"
    ITALIC: ClassVar[str] = "\033[3m"
    UNDERLINE: ClassVar[str] = "\033[4m"
    NO_UNDERLINE: ClassVar[str] = "\033[24m"

    CSI: ClassVar[str] = "\033["

    ANSI_ESCAPE_REGEX: ClassVar[Pattern[str]] = re.compile(r"\x1b\[[0-9;]*m")

    _CHANNEL_RANGE: ClassVar[str] = (
        "RGB channel {name}={value!r} is out of the 0..255 inclusive range."
    )

    @classmethod
    def rgb_fg(cls, red: int, green: int, blue: int) -> str:
        """24-bit SGR foreground (text colour) escape sequence."""
        channels: Tuple[int, int, int] = cls._validated(red, green, blue)

        return "\033[38;2;{};{};{}m".format(*channels)

    @classmethod
    def rgb_bg(cls, red: int, green: int, blue: int) -> str:
        """24-bit SGR background escape sequence."""
        channels: Tuple[int, int, int] = cls._validated(red, green, blue)

        return "\033[48;2;{};{};{}m".format(*channels)

    @classmethod
    def rgb_fg_bold(cls, red: int, green: int, blue: int) -> str:
        """24-bit SGR foreground escape with bold enabled."""
        channels: Tuple[int, int, int] = cls._validated(red, green, blue)

        return "\033[1;38;2;{};{};{}m".format(*channels)

    @classmethod
    def _validated(cls, red: int, green: int, blue: int) -> Tuple[int, int, int]:
        channels: Tuple[Tuple[str, int], ...] = (
            ("red", red),
            ("green", green),
            ("blue", blue),
        )
        if not all(isinstance(value, int) for _name, value in channels):
            raise TypeError(
                "RGB channels must be Python integers in the 0..255 range; "
                f"got (red={red!r}, green={green!r}, blue={blue!r})."
            )
        for name, value in channels:
            if not 0 <= value <= 255:
                raise ValueError(cls._CHANNEL_RANGE.format(name=name, value=value))

        return red, green, blue


class CheckOutcomeBadge:
    """
    Renders the outcome of a check as a padded, background-coloured badge.

    Same layout as :class:`SeverityBadge` — background, knocked-out
    foreground, one space of breathing room on each side — but a check has
    only two outcomes and neither of them is a severity: it held, or it
    did not.
    """

    PASSED_LABEL: ClassVar[str] = "OK"
    FAILED_LABEL: ClassVar[str] = "ERROR"

    _PASSED_BACKGROUND: ClassVar[Tuple[int, int, int]] = (22, 163, 74)
    _FAILED_BACKGROUND: ClassVar[Tuple[int, int, int]] = (153, 27, 27)
    _FOREGROUND: ClassVar[Tuple[int, int, int]] = (255, 255, 255)

    @classmethod
    def render(cls, passed: bool) -> str:
        """
        Return the badge for a check that held, or for one that did not.

        The badge is followed by as many plain spaces as it is narrower
        than the widest one, so a listing of both outcomes lines its
        labels up in one column while each block keeps its own width.
        """
        background: Tuple[int, int, int] = (
            cls._PASSED_BACKGROUND if passed else cls._FAILED_BACKGROUND
        )
        label: str = cls.PASSED_LABEL if passed else cls.FAILED_LABEL
        alignment: str = " " * (cls.width() - len(label) - 2)

        return (
            f"{TerminalColor.rgb_bg(*background)}"
            f"{TerminalColor.rgb_fg(*cls._FOREGROUND)}{TerminalColor.BOLD}"
            f" {label} "
            f"{TerminalColor.RESET}{alignment}"
        )

    @classmethod
    def width(cls) -> int:
        """
        Return how many columns the widest badge occupies.
        """
        return max(len(cls.PASSED_LABEL), len(cls.FAILED_LABEL)) + 2


class SeverityBadge:
    """
    Renders a severity level as a padded, background-coloured badge.

    The layout is always ``<BG><FG><BOLD> <GLYPH><LABEL> <RESET>``, with
    exactly one space of breathing room on each side.
    """
    _STYLES: ClassVar[Dict[str, Dict[str, object]]] = {
        "EMERGENCY": {
            "bg": (127, 0, 0),        # deep maroon (more restrained than pure red)
            "fg": (255, 255, 255),    # white foreground — maximum contrast
            "glyph": "🛑",
            "default_aliases": ("EMERG",),
        },
        "ALERT": {
            "bg": (220, 38, 38),      # bright red
            "fg": (255, 255, 255),
            "glyph": "🔔",
            "default_aliases": (),
        },
        "CRITICAL": {
            "bg": (185, 28, 28),      # darker red
            "fg": (255, 255, 255),
            "glyph": "💥",
            "default_aliases": ("CRIT",),
        },
        "ERROR": {
            "bg": (153, 27, 27),      # deep red
            "fg": (255, 255, 255),
            "glyph": "✖",
            "default_aliases": ("ERR",),
        },
        "WARNING": {
            "bg": (202, 138, 4),      # warm amber (WCAG-friendly vs. harsh yellow)
            "fg": (26, 18, 2),        # near-black foreground for readability
            "glyph": "⚠",
            "default_aliases": ("WARN",),
        },
        "NOTICE": {
            "bg": (21, 94, 117),       # cyan-800 (deep teal cyan, darker than INFO)
            "fg": (255, 255, 255),
            "glyph": "ℹ",
            "default_aliases": ("NOTE",),
        },
        "SUCCESS": {
            "bg": (22, 163, 74),      # green-600
            "fg": (255, 255, 255),
            "glyph": "✔",
            "default_aliases": ("OK",),
        },
        "INFO": {
            "bg": (14, 116, 144),      # cyan-700 (vivid teal cyan, lighter than NOTICE)
            "fg": (255, 255, 255),
            "glyph": "·",
            "default_aliases": ("INFORMATIONAL",),
        },
        "DEBUG": {
            "bg": (64, 64, 64),       # neutral slate-700 grey
            "fg": (226, 232, 240),    # very light grey foreground
            "glyph": "·",
            "default_aliases": ("DBG", "TRACE"),
        },
        "RUN": {
            "bg": (117, 117, 117),    # matches the terminal renderer's "neutral" theme
            "fg": (255, 255, 255),
            "glyph": "🤖",
            "default_aliases": (),
        },
    }

    @classmethod
    def render(
        cls,
        level: object,
        *,
        glyph: bool = True,
        fallback: Optional[str] = None,
    ) -> str:
        """Render ``level`` as a padded, background-coloured badge string.

        The badge layout is always ``<BG><FG><TerminalColor.BOLD> <GLYPH><LABEL> <TerminalColor.RESET>`` —
        exactly one space of breathing room on each side (user requirement).
        Empty string is returned for unknown levels unless a ``fallback``
        severity name (e.g. ``"INFO"``) is supplied.
        """
        severity: Optional[str] = cls._resolve(level)
        if severity is None:
            severity = cls._resolve(fallback)
        if severity is None:
            return ""
        style: Dict[str, object] = cls._STYLES[severity]
        bg_rgb: Tuple[int, int, int] = tuple(style["bg"])  # type: ignore[assignment]
        fg_rgb: Tuple[int, int, int] = tuple(style["fg"])  # type: ignore[assignment]
        glyph_ch: str = (str(style.get("glyph", "")) + " ") if glyph else ""
        label: str = severity.upper()
        return (
            f"{TerminalColor.rgb_bg(*bg_rgb)}{TerminalColor.rgb_fg(*fg_rgb)}{TerminalColor.BOLD}"
            f" {glyph_ch}{label} "
            f"{TerminalColor.RESET}"
        )

    @classmethod
    def _resolve(cls, level: object) -> Optional[str]:
        """Return the canonical ALL-CAPS severity key for ``level`` or ``None``.

        Accepts: ``LogLevelPort`` enums (reads ``.value``), plain strings
        (``"error"``, ``"WARN"``, …), or any object that can be stringified.
        Unknown values fall back to ``None`` so callers can default the badge
        off instead of inventing an unbranded colour.
        """
        raw: str = ""
        if level is None:
            return None
        if hasattr(level, "value"):
            raw = str(getattr(level, "value"))
        else:
            raw = str(level)
        key: str = raw.strip().upper()
        if key in cls._STYLES:
            return key
        for canonical, style in cls._STYLES.items():
            aliases = style.get("default_aliases") or ()
            if key in aliases:
                return canonical
        return None
