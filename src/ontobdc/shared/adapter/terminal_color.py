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
from typing import Tuple

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


# ---------------------------------------------------------------------------
# Compiled regex for stripping ANSI CSI sequences (same pattern previously
# duplicated in ``view/component/logo/python.py`` and
# ``view/adapter/terminal/surface_renderer.py``).  Compiling once here and
# reusing saves the per-module re-compile cost and guarantees identical
# matching semantics everywhere.
# ---------------------------------------------------------------------------
ANSI_ESCAPE_REGEX: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*m")
