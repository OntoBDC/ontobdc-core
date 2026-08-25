"""Centralized ANSI SGR terminal colour/style helpers.

Single source of truth for every terminal escape sequence used across the
OntoBDC codebase.  Duplicating these codes scattered through adapter
files is a source of subtle palette drift (the same ``GRAY`` being two
different SGR values in two different files) and of duplicated regex
compilations for the *same* ANSI-escape cleaner pattern.

Naming convention
-----------------
Constants are intentionally UPPER_CASE without any leading underscore so
they can be re-exported or aliased freely from different layers
(``cli`` / ``shared`` / ``view``).  Callers that want a private-looking
symbol should alias on import::

    from ontobdc.shared.adapter.terminal_color import (
        GRAY as _GRAY,
        RESET as _RESET,
    )

Rule #18 compliance
-------------------
Module-level helper *functions* are kept to the absolute minimum
(``rgb_fg`` / ``rgb_bg``) because they are pure, side-effect-free,
deterministic formatters with zero mutable state — the exact shape the
rule tolerates inside a dedicated single-purpose utility module.
Everything else (4-bit colours, SGR styles, regex pattern) is a plain
module constant.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# 4-bit foreground colours (SGR 30–37 + 90–97 for "bright" variants).
# Values are kept identical to the historical hardcoded constants in
# ``cli/adapter/logger.py`` so the rendered palette does not change.
# ---------------------------------------------------------------------------

# SGR 0 — Reset / Normal  (also resets background/style attributes)
RESET: str = "\033[0m"

# SGR 30 / bright 90-family — the canonical palette used by InLineLogger.
BLACK:     str = "\033[30m"
RED:       str = "\033[31m"
GREEN:     str = "\033[32m"
YELLOW:    str = "\033[33m"
BLUE:      str = "\033[34m"
MAGENTA:   str = "\033[35m"
CYAN:      str = "\033[36m"
WHITE:     str = "\033[37m"

# Bright variants  (SGR 90-family — "high intensity" palette).
# GRAY in particular is the exact SGR code used for the ``[HH:MM:SS]``
# timestamp on the inline logger ("Bright Black").
BRIGHT_BLACK:  str = "\033[90m"
BRIGHT_RED:    str = "\033[91m"
BRIGHT_GREEN:  str = "\033[92m"
BRIGHT_YELLOW: str = "\033[93m"
BRIGHT_BLUE:   str = "\033[94m"
BRIGHT_MAGENTA: str = "\033[95m"
BRIGHT_CYAN:   str = "\033[96m"
BRIGHT_WHITE:  str = "\033[97m"

# Convenience alias — everywhere else in the project this specific shade
# is always spelled ``GRAY`` (matching the historical ``_GRAY`` variable
# name from ``cli/adapter/logger.py``).
GRAY: str = BRIGHT_BLACK

# ---------------------------------------------------------------------------
# SGR styles (non-colour attributes).
# ---------------------------------------------------------------------------
BOLD:             str = "\033[1m"   # SGR 1 — bold / increased intensity
DIM:              str = "\033[2m"   # SGR 2 — dim / faint / decreased intensity
NORMAL_INTENSITY: str = "\033[22m"  # SGR 22 — cancels BOLD+DIM
ITALIC:           str = "\033[3m"   # SGR 3 — italic (if terminal supports)
UNDERLINE:        str = "\033[4m"   # SGR 4 — single underline
NO_UNDERLINE:     str = "\033[24m"  # SGR 24 — cancels UNDERLINE

# ---------------------------------------------------------------------------
# Non-SGR CSI sequences: cursor movement and line-level erasure.
# These are pure ANSI control primitives (not colours) but live here so
# every escape string flows through one adapter.
# ---------------------------------------------------------------------------

CSI: str = "\033["                              # Control Sequence Introducer

CURSOR_UP: str = f"{CSI}{{}}A"                  # Format with number of lines
CURSOR_UP_1: str = f"{CSI}1A"                   # Common case: move 1 line up
ERASE_LINE: str = f"{CSI}2K"                    # SGR 2K — erase entire line
CARRIAGE_RETURN: str = "\r"

# ---------------------------------------------------------------------------
# 24-bit "true colour" foreground / background helpers (SGR 38;2 / 48;2).
# ---------------------------------------------------------------------------

_VALID_RGB_RANGE: str = (
    "RGB channel {name}={value!r} is out of the 0..255 inclusive range."
)


def _validate_rgb(red: int, green: int, blue: int) -> Tuple[int, int, int]:
    """Raise ``ValueError`` if any channel is outside ``0 <= c <= 255``.

    Internal helper (leading underscore) because the two public
    one-liners below are the intended API surface.
    """
    if not (
        isinstance(red, int)
        and isinstance(green, int)
        and isinstance(blue, int)
    ):
        raise TypeError(
            "RGB channels must be Python integers in the 0..255 range; "
            f"got (red={red!r}, green={green!r}, blue={blue!r})."
        )
    for name, value in (("red", red), ("green", green), ("blue", blue)):
        if not (0 <= value <= 255):
            raise ValueError(_VALID_RGB_RANGE.format(name=name, value=value))
    return red, green, blue


def rgb_fg(red: int, green: int, blue: int) -> str:
    """Return a 24-bit SGR foreground (text colour) escape sequence.

    >>> rgb_fg(0, 180, 216)
    '\\x1b[38;2;0;180;216m'
    """
    r, g, b = _validate_rgb(red, green, blue)
    return f"\033[38;2;{r};{g};{b}m"


def rgb_bg(red: int, green: int, blue: int) -> str:
    """Return a 24-bit SGR background escape sequence.

    >>> rgb_bg(25, 70, 109)
    '\\x1b[48;2;25;70;109m'
    """
    r, g, b = _validate_rgb(red, green, blue)
    return f"\033[48;2;{r};{g};{b}m"


def rgb_fg_bold(red: int, green: int, blue: int) -> str:
    """Return a 24-bit SGR foreground escape with BOLD (SGR 1) enabled.

    >>> rgb_fg_bold(0, 180, 216)
    '\\x1b[1;38;2;0;180;216m'
    """
    r, g, b = _validate_rgb(red, green, blue)
    return f"\033[1;38;2;{r};{g};{b}m"


def cursor_up(lines: int) -> str:
    """Return a CSI CUU sequence that moves the cursor up ``lines`` rows.

    The cursor stops at the top margin (row 1) instead of wrapping.
    """
    if not isinstance(lines, int):
        raise TypeError(f"lines must be int; got {type(lines).__name__}")
    if lines <= 0:
        return ""
    return f"{CSI}{lines}A"


def erase_line() -> str:
    """Return the CSI EL sequence that erases the entire current line (SGR 2K)."""
    return ERASE_LINE


# ---------------------------------------------------------------------------
# Severity (RFC 5424 log level + SUCCESS) visual policy.
#
# The rendering contract is:
#   (1) Label is always ALL-CAPS  (matches user expectation: "INFO ERROR WARN").
#   (2) Label has 1 SPACE left padding + 1 SPACE right padding (breath).
#   (3) Background is the event colour; foreground is readable high-contrast
#       white or black (W3C AA contrast target).
#   (4) An optional one-codepoint glyph is emitted before the label when
#       the caller has Unicode support (default).  Set ``glyph=False`` on
#       ``severity_badge()`` to emit a text-only badge.
# ---------------------------------------------------------------------------


_SEVERITY_STYLES: Dict[str, Dict[str, object]] = {
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
}


def _resolve_severity(level: object) -> Optional[str]:
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
    if key in _SEVERITY_STYLES:
        return key
    for canonical, style in _SEVERITY_STYLES.items():
        aliases = style.get("default_aliases") or ()
        if key in aliases:
            return canonical
    return None


def severity_badge(
    level: object,
    *,
    glyph: bool = True,
    fallback: Optional[str] = None,
) -> str:
    """Render ``level`` as a padded, background-coloured badge string.

    The badge layout is always ``<BG><FG><BOLD> <GLYPH><LABEL> <RESET>`` —
    exactly one space of breathing room on each side (user requirement).
    Empty string is returned for unknown levels unless a ``fallback``
    severity name (e.g. ``"INFO"``) is supplied.
    """
    severity: Optional[str] = _resolve_severity(level)
    if severity is None:
        severity = _resolve_severity(fallback)
    if severity is None:
        return ""
    style: Dict[str, object] = _SEVERITY_STYLES[severity]
    bg_rgb: Tuple[int, int, int] = tuple(style["bg"])  # type: ignore[assignment]
    fg_rgb: Tuple[int, int, int] = tuple(style["fg"])  # type: ignore[assignment]
    glyph_ch: str = (str(style.get("glyph", "")) + " ") if glyph else ""
    label: str = severity.upper()
    return (
        f"{rgb_bg(*bg_rgb)}{rgb_fg(*fg_rgb)}{BOLD}"
        f" {glyph_ch}{label} "
        f"{RESET}"
    )


# ---------------------------------------------------------------------------
# Compiled regex for stripping ANSI CSI sequences (same pattern previously
# duplicated in ``view/component/logo/python.py`` and
# ``view/adapter/terminal/surface_renderer.py``).  Compiling once here and
# reusing saves the per-module re-compile cost and guarantees identical
# matching semantics everywhere.
# ---------------------------------------------------------------------------
ANSI_ESCAPE_REGEX: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*m")
