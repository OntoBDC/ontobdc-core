from abc import ABC, abstractmethod
from pathlib import Path

from ontobdc.shared.domain.model.draw import DrawSource


class DrawSourceStrategyPort(ABC):
    """Contract for plugins that understand drawing source content."""

    priority: int = 0

    @abstractmethod
    def accepts(self, source_path: Path) -> bool:
        """Return whether this plugin understands the source content."""
        ...

    @abstractmethod
    def load(self, source_path: Path) -> DrawSource:
        """Load the source into the normalized drawing representation."""
        ...


class SvgDrawPort(ABC):
    """Contract for drawing normalized content as SVG."""

    @abstractmethod
    def draw(self, source: DrawSource) -> str:
        """Return an SVG document representing the source."""
        ...
