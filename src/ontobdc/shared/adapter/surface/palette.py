from typing import ClassVar, Dict, Tuple


class SurfacePalette:
    """
    Single source for the RGB accent of every terminal surface theme.
    """
    THEMES: ClassVar[Dict[str, Tuple[int, int, int]]] = {
        "ontobdc": (0, 180, 216),
        "success": (46, 125, 50),
        "warning": (230, 140, 0),
        "error": (186, 26, 26),
        "info": (2, 119, 189),
        "neutral": (117, 117, 117),
    }
    DEFAULT_THEME: ClassVar[str] = "ontobdc"

    @classmethod
    def normalize(cls, theme: str) -> str:
        normalized_theme: str = str(theme or "").strip().lower()
        if normalized_theme not in cls.THEMES:
            return cls.DEFAULT_THEME

        return normalized_theme

    @classmethod
    def rgb_for(cls, theme: str) -> Tuple[int, int, int]:
        return cls.THEMES[cls.normalize(theme)]
