from typing import ClassVar, Dict


class SurfaceBox:
    """
    Unicode box-drawing characters used to frame a terminal surface.
    """
    CHARS: ClassVar[Dict[str, str]] = {
        "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
        "h": "─", "v": "│",
        "tt": "┬", "bt": "┴", "lt": "├", "rt": "┤",
        "x": "┼",
    }
