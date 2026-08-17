
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ontobdc.shared.domain.model.component import ComponentMetadata


class ComponentPort(ABC):
    """
    Base port for presentation Components discovered by ComponentLoader.

    A Component is a pure descriptor — its METADATA declares the
    custom-element tag it renders and the URIs an entity must satisfy for
    the component to match. Components have no behavior of their own;
    matching logic lives in ComponentLoader, not here.
    """
    METADATA: ComponentMetadata


class TerminalTileRenderable(ABC):
    """Rendering contract for a Tile that can produce ANSI/UTF-8 terminal
    output inside a Surface region.

    Implementations should honour the supplied ``columns`` x ``rows`` envelope
    (character cells) and return a newline-separated block sized to fit. Any
    formatting, colour codes, or Unicode box drawing is allowed; callers
    decide whether colour output is enabled via ``context["color"]``.
    """

    @abstractmethod
    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        ...
