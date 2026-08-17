from __future__ import annotations

from typing import Any, Dict, Optional

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.shared.domain.model.component import ComponentMetadata
from ontobdc.shared.domain.port.component import (
    ComponentPort,
    TerminalTileRenderable,
)
from ontobdc.view.component.logo.python import LogoComponent

_VIEW = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
).get_ontology_namespace_by_prefix("obdc_view")


class TerminalLogoTile(ComponentPort, TerminalTileRenderable):
    """Terminal 1x1 default rendering for the :view:`LogoTile` chrome tile.

    Reuses the existing ``LogoComponent.render_compact`` compact marker — the
    small ``>_ OntoBDC`` one-line brand — unchanged. The same
    ``view:LogoTile`` class is matched by both this terminal implementation
    (registered in the core ``ontobdc.view`` component tree) and the
    ``LogoTileComponent`` browser implementation (registered in
    ``ontobdc_view.component.plugin``). Which one runs is decided by the
    renderer (terminal Surface vs. HTML Surface), not by the matching step.
    """

    METADATA = ComponentMetadata(
        id="org.ontobdc.view.component.logo.terminal",
        tag="onto-logo-tile-terminal",
        tile_class=str(_VIEW.LogoTile),
        version="1.0.0",
        name="Logo Tile (Terminal)",
        description="Renders the compact 1x1 terminal brand marker.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["view", "surface", "tile", "chrome", "terminal", "branding"],
        supported_languages=["en", "pt-BR", "pt-PT", "es"],
        min_columns=1,
        max_columns=8,
        min_rows=1,
        max_rows=3,
    )

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        color: bool = True
        center: bool = False
        if context is not None:
            if "color" in context:
                color = bool(context["color"])
            if "center" in context:
                center = bool(context["center"])
        component = LogoComponent(center=center, color=color)
        return component.render_compact()
