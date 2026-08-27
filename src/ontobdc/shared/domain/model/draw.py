from dataclasses import dataclass
from enum import Enum


class DrawSourceKind(str, Enum):
    """Kinds of content understood by drawing capabilities."""

    RASTER = "raster"
    VECTOR = "vector"


@dataclass(frozen=True)
class DrawSource:
    """Source content normalized by a draw strategy plugin."""

    kind: DrawSourceKind
    source_format: str
    content_format: str
    content: bytes
    width: int
    height: int
