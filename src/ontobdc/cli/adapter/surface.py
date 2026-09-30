from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type

from ontobdc.shared.adapter.surface.box import SurfaceBox
from ontobdc.cli.component.tile.markdown import MarkdownBodyTile
from ontobdc.shared.adapter.terminal_text import TerminalTextMetrics
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.shared.adapter.surface.palette import SurfacePalette
from ontobdc.shared.domain.port.component import ComponentPort, TerminalTileRenderable
from ontobdc.shared.adapter.surface.selector import DefaultSurfaceLayoutSelector
from ontobdc.shared.domain.model.surface import (
    ComponentPlacementDefinition,
    RegionDefinition,
    RegionRole,
    SurfaceCapacity,
    SurfaceDefinition,
)


class TerminalSurfaceRenderer:
    """Render a ``SurfaceDefinition`` onto the terminal as a single unified
    UX frame that mirrors the HTML presentation layer layout.

    The layout is a single outer border (the "moldura") that encloses three
    vertical bands — **OperationRegion** (top chrome), **ContentRegion**
    (body, full-width by default), and **PinnedRegion** (bottom chrome) —
    plus any ``PresentationRegion`` tiles, which are drawn inside the
    ContentRegion's body area.

    How the "buracos na linha" work (exactly the HTML chrome mapping):

    * The **top border** is normally ``┌──────────────────────────────────┐``.
      Any tile placed in the **OperationRegion** *opens a cutout* in that
      top border line and sits flush inside the frame at that column
      offset, replacing the border glyphs with the tile's rendered content.
      This matches the HTML operation bar where the OntoBDC logo tile is
      the first element — the logo tile becomes the top-left cutout.
    * The **bottom border** is normally ``└──────────────────────────────────┘``.
      Any tile placed in the **PinnedRegion** opens a cutout in that bottom
      border line just like the top chrome.
    * The **ContentRegion** is always inner full-width (minus the two
      ``│`` side borders and one char of inner padding on each side), so
      a content tile "tenta pegar toda a largura, a menos que haja
      configuração contrária", as requested.
    * The *entire* border (top line, left/right verticals, bottom line)
      is rendered with a UX-tinted ANSI foreground color when
      ``color=True``, matching the HTML UI's theme-aware chrome.

    Tiles are still resolved via ``ComponentLoader.match_tile_class`` with
    the TerminalTileRenderable preference, exactly like the previous
    renderer — no architecture was replaced, only the framing math and
    region-to-band mapping changed to the HTML-like UX layout.
    """

    _BOX: Dict[str, str] = SurfaceBox.CHARS

    _PALETTE: Dict[str, Tuple[int, int, int]] = SurfacePalette.THEMES

    _BUILTIN_LOGO_TILE_IRI: str = "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#LogoTile"
    _BODY_TILE_IRI: str = "urn:ontobdc:terminal:tile:markdown-body"
    _OPERATION_OVERRIDE_TILE_IRI: str = "urn:ontobdc:terminal:tile:operation-override"

    def __init__(
        self,
        *,
        component_loader: Optional[Any] = None,
        color: bool = True,
        theme: str = "ontobdc",
        tiles: Optional[Dict[str, TerminalTileRenderable]] = None,
    ) -> None:
        self._loader: Any = component_loader or None
        self._color: bool = bool(color)
        self._theme_key: str = SurfacePalette.normalize(theme)
        self._tiles: Dict[str, TerminalTileRenderable] = dict(tiles or {})
        self._tile_cache: Dict[str, Type[ComponentPort]] = {}
        self._builtin_cache: Dict[str, Type[ComponentPort]] = {}

    def _ensure_loader(self) -> Any:
        if self._loader is None:
            from ontobdc.shared.adapter.loader import ComponentLoader  # noqa: WPS433

            self._loader = ComponentLoader()
        return self._loader

    def _builtin_tile_class(self, iri: str) -> Optional[Type[ComponentPort]]:
        """Hardcoded mapping for high-priority chrome tiles so the renderer
        can bootstrap without pulling in ``ComponentLoader`` at import time.

        The standard plugin discovery path in ``ComponentLoader`` (and its
        dependency chain through shared/facade) causes a circular import
        against ``ontobdc.cli``. The tiles here are the same objects the
        loader would return, just pre-resolved for their known canonical
        IRIs. Everything else still falls back to the loader on demand.
        """
        if iri in self._builtin_cache:
            return self._builtin_cache[iri]
        if iri == self._BUILTIN_LOGO_TILE_IRI:
            from ontobdc.cli.plugin.tile.logo import (  # noqa: WPS433
                TerminalLogoTile,
            )

            self._builtin_cache[iri] = TerminalLogoTile
            return TerminalLogoTile
        return None

    # ------------------------------------------------------------------ API

    def render(
        self,
        surface: SurfaceDefinition,
        *,
        capacity: SurfaceCapacity,
    ) -> str:
        if not surface.regions:
            return ""
        # Frame width always follows the real terminal (capacity.columns) so the
        # box occupies the full current width. surface.columns is a *declared*
        # layout constraint used only as a fallback when capacity is not
        # populated (should never happen in real usage).
        total_width: int = (
            capacity.columns
            if (capacity.columns or 0) > 4
            else (surface.columns or 80)
        )
        sorted_regions: List[RegionDefinition] = sorted(
            surface.regions,
            key=lambda r: ((r.row_start or 1), (r.column_start or 1)),
        )
        ops: List[RegionDefinition] = [
            r for r in sorted_regions if r.role == "OperationRegion"
        ]
        pinned: List[RegionDefinition] = [
            r for r in sorted_regions if r.role == "PinnedRegion"
        ]
        content_bands: List[RegionDefinition] = [
            r for r in sorted_regions if r.role != "OperationRegion" and r.role != "PinnedRegion"
        ]

        ops_rendered: List[Tuple[RegionDefinition, List[str]]] = []
        for region in ops:
            for placement in sorted(region.placements, key=lambda p: p.order):
                lines = self._render_tile_lines(
                    placement,
                    region=region,
                    tile_width=(region.column_span or max(10, total_width // 4)),
                    tile_height=(region.row_span or 1),
                    capacity=capacity,
                )
                ops_rendered.append((region, lines))

        pinned_rendered: List[Tuple[RegionDefinition, List[str]]] = []
        for region in pinned:
            for placement in sorted(region.placements, key=lambda p: p.order):
                lines = self._render_tile_lines(
                    placement,
                    region=region,
                    tile_width=(region.column_span or max(10, total_width // 4)),
                    tile_height=(region.row_span or 1),
                    capacity=capacity,
                )
                pinned_rendered.append((region, lines))

        content_lines: List[str] = []
        for region in content_bands:
            rendered_region: List[str] = self._render_content_region(
                region, capacity=capacity, total_width=total_width
            )
            if rendered_region:
                if content_lines:
                    content_lines.append("")
                content_lines.extend(rendered_region)

        return self._assemble_frame(
            total_width=total_width,
            operation_tiles=ops_rendered,
            content_lines=content_lines,
            pinned_tiles=pinned_rendered,
        )

    # --------------------------------------------------------------- default

    @classmethod
    def default_logo_only_surface(cls) -> SurfaceDefinition:
        """Mirror the HTML default surface on the terminal side:

        * **OperationRegion (row 1, full terminal width)** — logo tile placed
          as the first cutout on the top border ("abre o buraco na linha").
        * **ContentRegion (row 2..N-1, full terminal width)** — empty
          placeholder body for the actual command output.
        * **PinnedRegion (row N, full terminal width)** — empty chrome band
          at the bottom border, ready for pinned tiles to open their cutouts.

        ``column_span`` is intentionally left as ``None`` so the render loop
        uses the real terminal columns returned by
        ``shutil.get_terminal_size()``.  Hard-coding 80 here used to clamp
        the body layout (and every inner table) to 76 visible columns even
        when the terminal was 300+ columns wide — that was the root cause
        of "a tabela não ocupa toda a largura do box" when the renderer
        correctly locked table width to the narrow region allocation.
        """
        logo_iri = "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#LogoTile"
        return SurfaceDefinition(
            iri="urn:ontobdc:terminal:surface:logo-only",
            columns=80,
            rows=10,
            is_default_layout=True,
            layout_priority=0,
            min_available_columns=20,
            min_available_rows=5,
            regions=[
                RegionDefinition(
                    iri="urn:ontobdc:terminal:region:operation",
                    role="OperationRegion",
                    row_start=1,
                    column_start=1,
                    row_span=1,
                    column_span=None,
                    placements=[
                        ComponentPlacementDefinition(
                            iri="urn:ontobdc:terminal:placement:logo",
                            component_iri=logo_iri,
                            component_type_iri=logo_iri,
                            alignment="start",
                            order=0,
                        ),
                    ],
                ),
                RegionDefinition(
                    iri="urn:ontobdc:terminal:region:content",
                    role="ContentRegion",
                    row_start=2,
                    column_start=1,
                    row_span=8,
                    column_span=None,
                    placements=[],
                    scrollable=True,
                ),
                RegionDefinition(
                    iri="urn:ontobdc:terminal:region:pinned",
                    role="PinnedRegion",
                    row_start=10,
                    column_start=1,
                    row_span=1,
                    column_span=None,
                    placements=[],
                ),
            ],
        )

    @classmethod
    def with_content_surface(
        cls,
        body_markdown: str,
        *,
        theme: str = "ontobdc",
        capacity: Optional[SurfaceCapacity] = None,
        operation_tile_iri: Optional[str] = None,
        operation_tile: Optional[Any] = None,
    ) -> str:
        """Helper used by the CLI render path: wrap a markdown body string
        with the default logo-only Surface (operation=logo cutout,
        pinned=empty, content=body).

        Callers can optionally override the default builtin OntoBDC logo tile
        in the ``OperationRegion`` by passing either:

        * ``operation_tile_iri`` (a ``component_type_iri`` override that the
          usual ``_resolve_tile`` lookup will use the dynamic registry for);
          or
        * ``operation_tile`` (a ready-made ``TerminalTileRenderable``
          instance that will be registered in the dynamic tile registry
          under a synthetic internal IRI so branding can be completely
          plugged without having to touch the renderer's component loader).

        This is how consumers that reuse the shared renderer (e.g. the
        InfoBIM companion CLI) plug their own brand tile in place of the
        default ``>_ OntoBDC`` logo without needing to re-implement surface
        assembly or frame drawing.
        """
        surface: SurfaceDefinition = cls.default_logo_only_surface()
        # --- OperationRegion branding swap ------------------------------
        ops_regions: List[RegionDefinition] = [
            r for r in surface.regions if r.role == "OperationRegion"
        ]
        tiles: Dict[str, TerminalTileRenderable] = {}
        if operation_tile is not None:
            operation_tile_iri = cls._OPERATION_OVERRIDE_TILE_IRI
            tiles[operation_tile_iri] = operation_tile
        if operation_tile_iri is not None:
            for region in ops_regions:
                for placement in region.placements:
                    placement.component_iri = operation_tile_iri
                    placement.component_type_iri = operation_tile_iri
        # --- body tile ---------------------------------------------------
        for region in surface.regions:
            if region.role == "ContentRegion":
                region.placements = [
                    ComponentPlacementDefinition(
                        iri="urn:ontobdc:terminal:placement:body",
                        component_iri=cls._BODY_TILE_IRI,
                        component_type_iri=cls._BODY_TILE_IRI,
                        alignment="start",
                        order=0,
                    ),
                ]
                break
        if capacity is None:
            capacity = cls._default_capacity()
        tiles[cls._BODY_TILE_IRI] = MarkdownBodyTile(
            markdown=body_markdown,
            theme=theme,
        )
        # cls, not the base class by name: called on a subclass (see
        # BorderlessTerminalSurfaceRenderer), this must build one of that
        # subclass, or its own override of _assemble_frame would never run.
        renderer = cls(theme=theme, tiles=tiles)
        return renderer.render(surface, capacity=capacity)

    @classmethod
    def select_and_render(
        cls,
        *,
        capacity: Optional[SurfaceCapacity] = None,
        candidates: Optional[List[SurfaceDefinition]] = None,
        renderer: Optional["TerminalSurfaceRenderer"] = None,
        body_markdown: Optional[str] = None,
    ) -> str:
        if capacity is None:
            capacity = cls._default_capacity()
        if candidates is None:
            candidates = [cls.default_logo_only_surface()]
        surface: Optional[SurfaceDefinition] = (
            DefaultSurfaceLayoutSelector.select_default_layout(capacity, candidates)
        )
        if surface is None:
            surface = cls.default_logo_only_surface()
        active_renderer: TerminalSurfaceRenderer = renderer or cls()
        if body_markdown is not None:
            return cls.with_content_surface(
                body_markdown,
                theme=active_renderer._theme_key,
                capacity=capacity,
            )
        return active_renderer.render(surface, capacity=capacity)

    # ------------------------------------------------------------ internals

    @staticmethod
    def _default_capacity() -> SurfaceCapacity:
        import shutil

        cols, lines = shutil.get_terminal_size(fallback=(80, 24))
        return SurfaceCapacity(columns=cols, rows=lines)

    def _render_tile_lines(
        self,
        placement: ComponentPlacementDefinition,
        *,
        region: RegionDefinition,
        tile_width: int,
        tile_height: int,
        capacity: SurfaceCapacity,
    ) -> List[str]:
        tile: Optional[TerminalTileRenderable] = self._resolve_tile(placement)
        if tile is None:
            return [""]
        cols: int = max(2, tile_width - 2)
        rows: int = max(1, tile_height)
        rendered: str = tile.render(
            columns=cols,
            rows=rows,
            context={"color": self._color, "theme": self._theme_key},
        )
        return rendered.splitlines() or [""]

    def _render_content_region(
        self,
        region: RegionDefinition,
        *,
        capacity: SurfaceCapacity,
        total_width: int,
    ) -> List[str]:
        if region.role == "PresentationRegion":
            title: str = self._region_title(region)
            width: int = region.column_span or max(20, total_width - 2)
            content_lines: List[str] = self._render_placements_body(
                region, width=width, capacity=capacity, total_width=total_width
            )
            return self._frame_inner_panel(title=title, lines=content_lines, width=width, total_width=total_width)
        content_lines = self._render_placements_body(
            region,
            width=(region.column_span or max(20, total_width - 2)),
            capacity=capacity,
            total_width=total_width,
        )
        return content_lines

    def _render_placements_body(
        self,
        region: RegionDefinition,
        *,
        width: int,
        capacity: SurfaceCapacity,
        total_width: int,
    ) -> List[str]:
        _ = capacity
        inner_width: int = max(2, min(width, total_width) - 4)
        lines: List[str] = []
        for placement in sorted(region.placements, key=lambda p: p.order):
            tile = self._resolve_tile(placement)
            if tile is None:
                continue
            rendered = tile.render(
                columns=inner_width,
                rows=max(1, (region.row_span or 10)),
                context={"color": self._color, "theme": self._theme_key},
            )
            lines.extend(rendered.splitlines() or [""])
        return lines or [""]

    def _resolve_tile(
        self,
        placement: ComponentPlacementDefinition,
    ) -> Optional[TerminalTileRenderable]:
        tile_class: Optional[str] = placement.component_type_iri
        if not tile_class:
            return None
        if tile_class in self._tiles:
            return self._tiles[tile_class]
        if tile_class in self._tile_cache:
            component_cls: Any = self._tile_cache[tile_class]
            if callable(component_cls) and isinstance(component_cls, type):
                try:
                    return component_cls()
                except Exception:
                    return None
            return component_cls
        builtin_cls: Optional[Type[ComponentPort]] = self._builtin_tile_class(tile_class)
        if builtin_cls is not None and issubclass(builtin_cls, TerminalTileRenderable):
            self._tile_cache[tile_class] = builtin_cls
            try:
                return builtin_cls()
            except Exception:
                return None
        loader: Any = self._ensure_loader()
        matches: List[Any] = loader.match_tile_class(tile_class)
        if not matches:
            return None
        terminal_impl = next(
            (c for c in matches if issubclass(c, TerminalTileRenderable)),
            matches[0],
        )
        self._tile_cache[tile_class] = terminal_impl
        if not issubclass(terminal_impl, TerminalTileRenderable):
            return None
        try:
            return terminal_impl()
        except Exception:
            return None

    # -------------------------------------------------------- frame assembly

    def _assemble_frame(
        self,
        *,
        total_width: int,
        operation_tiles: List[Tuple[RegionDefinition, List[str]]],
        content_lines: List[str],
        pinned_tiles: List[Tuple[RegionDefinition, List[str]]],
    ) -> str:
        B = self._BOX
        inner_width: int = max(4, total_width - 2)

        top_line_parts: List[str] = [B["h"]] * inner_width
        bottom_line_parts: List[str] = [B["h"]] * inner_width

        # (align, inner_pad, left_margin, right_margin)
        # - inner_pad: whitespace "breathing" chars added inside the cutout,
        #   before and after every tile line (>=1 requested for logo).
        # - left/right_margin: box-line chars (`─`) left untouched between the
        #   cutout cluster and the left/right frame corner (2 requested on the
        #   right side of the top operation bar).
        CutoutMeta = Tuple[int, List[str], bool]  # start_col, padded_lines, divider_on_right

        def open_cutouts(
            tile_list: List[Tuple[RegionDefinition, List[str]]],
            *,
            line_parts: List[str],
            align: str = "left",
            inner_pad: int = 0,
            left_margin: int = 0,
            right_margin: int = 0,
        ) -> List[CutoutMeta]:
            if not tile_list:
                return []

            tile_bundles: List[Tuple[List[str], int]] = []  # (padded_lines, padded_w)
            for _region, raw_lines in tile_list:
                visible_widths: List[int] = [self._visible_length(line) for line in raw_lines]
                tile_content_w: int = max(1, max(visible_widths) if visible_widths else 1)
                padded_w: int = tile_content_w + inner_pad + inner_pad
                left_pad: str = " " * inner_pad
                right_pad: str = " " * inner_pad
                padded_lines: List[str] = []
                for ln in raw_lines:
                    visible = self._visible_length(ln)
                    fill: str = " " * max(0, tile_content_w - visible)
                    padded_lines.append(left_pad + ln + fill + right_pad)
                tile_bundles.append((padded_lines, padded_w))

            n_tiles: int = len(tile_bundles)
            total_padded: int = sum(w for _l, w in tile_bundles) + max(0, n_tiles - 1)  # + divider between

            if align == "right":
                # Place from the rightmost tile (first in list = rightmost visually)
                # walking leftwards; keep `right_margin` box-line chars before the frame corner.
                cursor_end: int = inner_width - right_margin  # first cell to the RIGHT of the rightmost cutout end
                cutouts: List[CutoutMeta] = []
                for idx, (padded_lines, padded_w) in enumerate(tile_bundles):
                    start: int = cursor_end - padded_w
                    if start < left_margin:
                        break
                    end: int = cursor_end
                    for i in range(start, end):
                        line_parts[i] = " "
                    # Divider `│` on the RIGHT side of this cutout?
                    # For right-aligned clusters the RIGHTMOST tile (idx 0) has
                    # no divider; the others (to its left) do.
                    divider_on_right: bool = idx > 0
                    cutouts.append((start, padded_lines, divider_on_right))
                    cursor_end = start - (1 if idx + 1 < n_tiles else 0)
                # We built the list right→left, but render it left→right in the
                # merge step (so start_cols grow). Reverse.
                cutouts.reverse()
                return cutouts

            # Left-to-right flow
            cursor: int = left_margin
            cutouts = []
            for idx, (padded_lines, padded_w) in enumerate(tile_bundles):
                start = cursor
                end = min(inner_width - right_margin, start + padded_w)
                if end <= start:
                    break
                for i in range(start, end):
                    line_parts[i] = " "
                # Divider only between tiles, never after the last one.
                divider_on_right = idx + 1 < n_tiles
                cutouts.append((start, padded_lines, divider_on_right))
                cursor = end + (1 if divider_on_right else 0)
            return cutouts

        ops_cutouts: List[Tuple[int, List[str], bool]] = open_cutouts(
            operation_tiles,
            line_parts=top_line_parts,
            align="left",
            inner_pad=1,
            left_margin=2,
        )

        top_line: str = self._color_border(
            B["tl"] + "".join(top_line_parts) + B["tr"]
        )

        body_padded: List[str] = []
        for raw in content_lines or [""]:
            body_padded.append(
                self._color_border(B["v"])
                + self._inner_pad_line(raw, total_width, framed=True)
                + self._color_border(B["v"])
            )

        pinned_cutouts: List[Tuple[int, List[str], bool]] = open_cutouts(
            pinned_tiles,
            line_parts=bottom_line_parts,
            align="left",
            inner_pad=1,
            left_margin=1,
        )
        bottom_line: str = self._color_border(
            B["bl"] + "".join(bottom_line_parts) + B["br"]
        )

        header_lines: List[str] = []
        if ops_cutouts:
            merged = self._merge_cutout_header(
                border_line=top_line,
                cutouts=ops_cutouts,
                inner_width=inner_width,
            )
            header_lines.extend(merged)
        else:
            header_lines.append(top_line)

        # Vertical breathing room: one empty body line under the operation
        # chrome so the content does not feel glued to the logo cutout.
        if ops_cutouts:
            empty_body_line = (
                self._color_border(B["v"])
                + self._inner_pad_line("", total_width, framed=True)
                + self._color_border(B["v"])
            )
            body_padded.insert(0, empty_body_line)

        footer_lines: List[str] = []
        if pinned_cutouts:
            merged = self._merge_cutout_header(
                border_line=bottom_line,
                cutouts=pinned_cutouts,
                inner_width=inner_width,
                is_bottom=True,
            )
            footer_lines.extend(merged)
        else:
            footer_lines.append(bottom_line)

        # Outer breathing: one blank line before the frame and one after.
        body: str = "\n".join(header_lines + body_padded + footer_lines)
        return f"\n{body}\n\n"

    def _merge_cutout_header(
        self,
        *,
        border_line: str,
        cutouts: List[Tuple[int, List[str], bool]],
        inner_width: int,
        is_bottom: bool = False,
    ) -> List[str]:
        B = self._BOX
        if not cutouts:
            return [border_line]

        # Parse the styled border line into a parallel structure of:
        # * run of styling (SGR escape sequences) active at the next cell
        # * the (unpadded visible glyph) at each cell (length 1)
        # Both lists are indexed by printable cell offset 0..len-1.
        styles: List[str] = []
        glyphs: List[str] = []
        active_style: str = ""
        idx = 0
        n = len(border_line)
        while idx < n:
            ch = border_line[idx]
            if ch == TerminalColor.CSI[0]:
                if not border_line.startswith(TerminalColor.CSI, idx):
                    glyphs.append(ch)
                    styles.append(active_style)
                    idx += 1
                    continue
                end = border_line.find("m", idx)
                if end == -1:
                    break
                seq = border_line[idx : end + 1]
                if seq == TerminalColor.RESET:
                    active_style = ""
                else:
                    active_style = active_style + seq
                idx = end + 1
                continue
            glyphs.append(ch)
            styles.append(active_style)
            idx += 1

        max_lines: int = max(1, max(len(t) for _, t, _d in cutouts)) if cutouts else 1
        # Each output line is a list of (style, glyph) pairs; we emit 1 cell
        # per slot so visible column count is preserved independently of
        # styling length.
        rows: List[List[Tuple[str, str]]] = [
            [(styles[i], glyphs[i]) for i in range(len(glyphs))]
            for _ in range(max_lines)
        ]
        V = B["v"]
        default_style: str = self._border_color_prefix()

        for start_col, tile_lines, divider_on_right in cutouts:
            tile_visible_width: int = max(
                1,
                max(self._visible_length(l) for l in tile_lines) if tile_lines else 1,
            )
            tile_full_start: int = 1 + start_col
            tile_full_end: int = 1 + min(inner_width, start_col + tile_visible_width)
            for y in range(max_lines):
                row = rows[y]
                if y < len(tile_lines):
                    tile_text = tile_lines[y]
                    visible = self._visible_length(tile_text)
                    x_out = tile_full_start
                    ti = 0
                    tlen = len(tile_text)
                    active: str = ""
                    visible_count = 0
                    while ti < tlen and x_out < len(row) - 1 and visible_count < visible:
                        ch = tile_text[ti]
                        if ch == TerminalColor.CSI[0]:
                            if not tile_text.startswith(TerminalColor.CSI, ti):
                                row[x_out] = (active, ch)
                                x_out += 1
                                ti += 1
                                visible_count += 1
                                continue
                            end = tile_text.find("m", ti)
                            if end == -1:
                                break
                            seq = tile_text[ti : end + 1]
                            if seq == TerminalColor.RESET:
                                active = ""
                            else:
                                active = active + seq
                            ti = end + 1
                            continue
                        row[x_out] = (active, ch)
                        x_out += 1
                        ti += 1
                        visible_count += 1
                # Vertical separator on the right edge of the cutout is only
                # drawn between tiles inside the same cluster; a single tile
                # has no divider (user explicitly said the lone `│` is
                # meaningless).
                if divider_on_right and tile_full_end < len(row) - 1:
                    _old_style, _old_glyph = row[tile_full_end]
                    rows[y][tile_full_end] = (default_style, V)

        out: List[str] = []
        reset: str = TerminalColor.RESET if self._color else ""
        for row in rows:
            parts: List[str] = []
            running: str = ""
            for style, glyph in row:
                if style != running:
                    if running and not style:
                        parts.append(reset)
                    elif style:
                        parts.append(style)
                    running = style
                parts.append(glyph)
            if running and reset:
                parts.append(reset)
            out.append("".join(parts))
        return out

    def _border_color_prefix(self) -> str:
        if not self._color:
            return ""
        r, g, b = self._PALETTE[self._theme_key]
        return TerminalColor.rgb_fg(r, g, b)

    # ---------------------------------------------------- title / small misc

    def _region_title(self, region: RegionDefinition) -> str:
        role: RegionRole = region.role
        if role == "PresentationRegion":
            return "OntoBDC"
        if role == "PinnedRegion":
            return "Pinned"
        if role == "OperationRegion":
            return "Operations"
        if role == "ContentRegion":
            return "Content"
        return role

    def _frame_inner_panel(
        self, *, title: str, lines: List[str], width: int, total_width: int
    ) -> List[str]:
        B = self._BOX
        inner: int = max(4, min(width, total_width - 4) - 2)
        title_seg = f" {title} "
        title_vis = self._visible_length(title_seg)
        if title_vis > inner:
            title_seg = TerminalTextMetrics.truncate_visible(
                title_seg, max(1, inner - 2)
            )
            title_vis = self._visible_length(title_seg)
        dashes = max(0, inner - title_vis)
        top = (
            self._color_border(B["lt"])
            + self._color_border(B["h"] + title_seg + B["h"] * dashes)
            + self._color_border(B["rt"])
        )
        rows: List[str] = [top]
        for raw in lines:
            vis = self._visible_length(raw)
            pad = max(0, inner - vis)
            rows.append(
                self._color_border(B["v"])
                + f" {raw}{' ' * pad} "
                + self._color_border(B["v"])
            )
        rows.append(
            self._color_border(B["bl"])
            + self._color_border(B["h"] * inner)
            + self._color_border(B["br"])
        )
        return [self._center_to_inner(row, total_width) for row in rows]

    def _inner_pad_line(self, raw: str, total_width: int, *, framed: bool = True) -> str:
        inner = max(2, total_width - (2 if framed else 0))
        vis = self._visible_length(raw)
        pad = max(0, inner - vis - 2)
        return f" {raw}{' ' * pad} "

    def _center_to_inner(self, line: str, total_width: int) -> str:
        inner = max(2, total_width - 2)
        vis = self._visible_length(line)
        if vis >= inner:
            return line
        left = (inner - vis) // 2
        right = inner - vis - left
        return " " * left + line + " " * right

    # ---------------------------------------------------- ANSI color helpers

    def _color_border(self, text: str) -> str:
        if not self._color:
            return text
        r, g, b = self._PALETTE[self._theme_key]
        return f"{TerminalColor.rgb_fg(r, g, b)}{text}{TerminalColor.RESET}"

    def _color_border_simple(self, char: str) -> str:
        if not self._color:
            return char
        r, g, b = self._PALETTE[self._theme_key]
        return f"{TerminalColor.rgb_fg(r, g, b)}{char}{TerminalColor.RESET}"

    @classmethod
    def _visible_length(cls, value: str) -> int:
        # Wide/emoji-aware: a naive ``len()`` under-counts glyphs like the
        # folder/file icons TreeWidget uses (they occupy 2 terminal columns
        # but are 1 Python codepoint), which made this shared measurer used
        # by the outer box assembly (_frame_inner_panel, _center_to_inner,
        # …) think such lines were shorter than they really are and pad
        # them with extra trailing spaces — pushing the real terminal past
        # its column count and causing it to soft-wrap the line, which
        # looked like a stray blank line breaking the tree's guides.
        return TerminalTextMetrics.visible_width(value)


class BorderlessTerminalSurfaceRenderer(TerminalSurfaceRenderer):
    """Render the same tiles ``TerminalSurfaceRenderer`` does, without the
    outer box frame.

    ``_default_capacity`` falls back to a guessed 80 columns whenever the
    caller has no real TTY to query (``shutil.get_terminal_size``'s own
    fallback) -- a pipe to a subprocess, for instance. The box frame only
    lines up when that guess matches the surface it is actually displayed
    on; a caller whose real width is unknown and possibly much narrower
    (an embedded terminal panel in a browser tab, say) gets a frame whose
    corners and side rules do not land where the display wraps its lines,
    which reads as broken far more than plain, unframed text ever does.

    Every tile still renders exactly as it does in the framed surface —
    same colors, same content, same resolution — only the final
    box-drawing step is skipped, so this is a straight subclass rather
    than a second renderer built from scratch.
    """

    def _assemble_frame(
        self,
        *,
        total_width: int,
        operation_tiles: List[Tuple[RegionDefinition, List[str]]],
        content_lines: List[str],
        pinned_tiles: List[Tuple[RegionDefinition, List[str]]],
    ) -> str:
        _ = total_width
        lines: List[str] = []
        for _region, tile_lines in operation_tiles:
            lines.extend(tile_lines)
        if operation_tiles:
            # The framed surface gives the operation chrome (the logo) its
            # own blank body line before the content starts; this keeps
            # that same breathing room instead of running content flush
            # against the brand line.
            lines.append("")
        lines.extend(content_lines)
        for _region, tile_lines in pinned_tiles:
            lines.extend(tile_lines)
        return "\n" + "\n".join(lines) + "\n\n"

