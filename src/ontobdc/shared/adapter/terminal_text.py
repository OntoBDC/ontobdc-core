import unicodedata
from typing import ClassVar, List, Tuple

from ontobdc.shared.adapter.terminal_color import TerminalColor


class TerminalTextMetrics:
    """
    Display width of terminal text, in character cells.

    Terminal-rendered emoji occupy two display columns in virtually every
    modern terminal emulator, but Python's Unicode database does not report
    all of them as wide: a few common ones, such as U+1F5C2 CARD INDEX
    DIVIDERS, come back neutral. Any width computed from the code point
    count alone would under-count those lines by one column each, pushing
    the line past the frame's right edge. The range table covers the emoji
    blocks used by the renderer's widgets.
    """
    _WIDE_EMOJI_RANGES: ClassVar[Tuple[Tuple[int, int], ...]] = (
        (0x1F300, 0x1F5FF),
        (0x1F600, 0x1F64F),
        (0x1F680, 0x1F6FF),
        (0x1F900, 0x1F9FF),
        (0x1FA70, 0x1FAFF),
    )
    _WIDE_EAST_ASIAN_WIDTHS: ClassVar[Tuple[str, ...]] = ("W", "F")

    @classmethod
    def character_width(cls, character: str) -> int:
        code_point: int = ord(character)
        for start, end in cls._WIDE_EMOJI_RANGES:
            if start <= code_point <= end:
                return 2
        east_asian_width: str = unicodedata.east_asian_width(character)

        return 2 if east_asian_width in cls._WIDE_EAST_ASIAN_WIDTHS else 1

    @classmethod
    def width_of(cls, text: str) -> int:
        return sum(cls.character_width(character) for character in text)

    @classmethod
    def visible_width(cls, text: str) -> int:
        """
        Width of the text as displayed, ignoring ANSI escape sequences.
        """
        return cls.width_of(TerminalColor.ANSI_ESCAPE_REGEX.sub("", text))

    @classmethod
    def truncate_visible(cls, text: str, width: int) -> str:
        """
        Truncate to at most the given number of visible characters.

        Every escape sequence encountered so far is preserved, so the
        colour and styling state stays consistent downstream. Plain text
        takes the fast slice path.
        """
        if width <= 0:
            return ""
        if not TerminalColor.ANSI_ESCAPE_REGEX.search(text):
            return text[:width]
        chars: List[str] = list(text)
        out_chars: List[str] = []
        glyphs_remaining: int = width
        index: int = 0
        total: int = len(chars)
        csi: str = TerminalColor.CSI
        while index < total and glyphs_remaining > 0:
            if chars[index] == csi[0] and "".join(chars[index:index + len(csi)]) == csi:
                end: int = index
                while end < total and chars[end] != "m":
                    end += 1
                if end < total:
                    out_chars.extend(chars[index:end + 1])
                    index = end + 1
                else:
                    index = total
            else:
                out_chars.append(chars[index])
                glyphs_remaining -= 1
                index += 1

        return "".join(out_chars)
