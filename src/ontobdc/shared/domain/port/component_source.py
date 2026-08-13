
from abc import ABC, abstractmethod
from typing import Optional


class ComponentSourcePort(ABC):
    """Resolves a Tile's ready-to-embed JavaScript source by custom-element tag.

    Covers both plain content Tiles (source read and returned as-is) and
    "system" Tiles (logo/theme/language/photo) whose JS carries a
    build-time placeholder that must be resolved with project data before
    the source is embeddable. The caller (`SurfacePackagedCapability`)
    only needs a tag; it has no knowledge of which Tiles are which kind —
    that decision belongs entirely to the adapter, in `ontobdc_view`.
    """

    @abstractmethod
    def component_source(self, tag: str) -> Optional[str]:
        """Return `tag`'s ready-to-embed JS source, or None if unavailable."""
