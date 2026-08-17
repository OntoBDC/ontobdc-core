from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type

from ontobdc.shared.adapter.surface.selector import DefaultSurfaceLayoutSelector
from ontobdc.shared.adapter.terminal_color import ANSI_ESCAPE_REGEX
from ontobdc.shared.domain.model.surface import (
    ComponentPlacementDefinition,
    RegionDefinition,
    RegionRole,
    SurfaceCapacity,
    SurfaceDefinition,
)
from ontobdc.shared.domain.port.component import (
    ComponentPort,
    TerminalTileRenderable,
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

    _BOX: Dict[str, str] = {
        "tl": "\u250c", "tr": "\u2510", "bl": "\u2514", "br": "\u2518",
        "h": "\u2500", "v": "\u2502",
        "tt": "\u252c", "bt": "\u2534", "lt": "\u251c", "rt": "\u2524",
        "x": "\u253c",
    }

    _PALETTE: Dict[str, Tuple[int, int, int]] = {
        "ontobdc": (0, 180, 216),
        "success": (46, 125, 50),
        "warning": (230, 140, 0),
        "error": (186, 26, 26),
        "info": (2, 119, 189),
        "neutral": (117, 117, 117),
    }

    _DYNAMIC_TILE_REGISTRY: Dict[str, Tuple[Type[TerminalTileRenderable], Optional[TerminalTileRenderable]]] = {}
    _BUILTIN_LOGO_TILE_IRI: str = "http://datacenter.app.br/ontology/ontobdc/domain/view.ttl#LogoTile"

    def __init__(
        self,
        *,
        component_loader: Optional[Any] = None,
        color: bool = True,
        theme: str = "ontobdc",
    ) -> None:
        self._loader: Any = component_loader or None
        self._color: bool = bool(color)
        theme_key: str = str(theme).strip().lower()
        if theme_key not in self._PALETTE:
            theme_key = "ontobdc"
        self._theme_key: str = theme_key
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
            from ontobdc.view.plugin.component.logo_tile import (  # noqa: WPS433
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
        synthetic_iri: Optional[str] = None
        if operation_tile is not None:
            synthetic_iri = "urn:ontobdc:terminal:tile:operation-override"
            TerminalSurfaceRenderer._DYNAMIC_TILE_REGISTRY[synthetic_iri] = (
                type(operation_tile),
                operation_tile,
            )
            operation_tile_iri = synthetic_iri
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
                        component_iri="urn:ontobdc:terminal:tile:markdown-body",
                        component_type_iri="urn:ontobdc:terminal:tile:markdown-body",
                        alignment="start",
                        order=0,
                    ),
                ]
                break
        if capacity is None:
            capacity = cls._default_capacity()
        renderer = TerminalSurfaceRenderer(theme=theme)
        renderer._DYNAMIC_TILE_REGISTRY["urn:ontobdc:terminal:tile:markdown-body"] = (
            _make_markdown_body_tile(body_markdown),
            None,
        )
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
            if isinstance(tile, _MarkdownBodyTile):
                tile._owner_renderer = self
                tile_lines = tile.render_wrapped(inner_width)
            else:
                rendered = tile.render(
                    columns=inner_width,
                    rows=max(1, (region.row_span or 10)),
                    context={"color": self._color, "theme": self._theme_key},
                )
                tile_lines = rendered.splitlines() or [""]
            lines.extend(tile_lines)
        return lines or [""]

    def _resolve_tile(
        self,
        placement: ComponentPlacementDefinition,
    ) -> Optional[TerminalTileRenderable]:
        tile_class: Optional[str] = placement.component_type_iri
        if not tile_class:
            return None
        if tile_class in self._DYNAMIC_TILE_REGISTRY:
            _cls, instance = self._DYNAMIC_TILE_REGISTRY[tile_class]
            if instance is not None:
                return instance
            try:
                return _cls()
            except Exception:
                return None
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
            if ch == "\x1b":
                end = border_line.find("m", idx)
                if end == -1:
                    break
                seq = border_line[idx : end + 1]
                if seq == "\x1b[0m":
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
                        if ch == "\x1b":
                            end = tile_text.find("m", ti)
                            if end == -1:
                                break
                            seq = tile_text[ti : end + 1]
                            if seq == "\x1b[0m":
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
        reset: str = "\x1b[0m" if self._color else ""
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
        return f"\x1b[38;2;{r};{g};{b}m"

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
            title_seg = title_seg[: max(1, inner - 2)]
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
        return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"

    def _color_border_simple(self, char: str) -> str:
        if not self._color:
            return char
        r, g, b = self._PALETTE[self._theme_key]
        return f"\x1b[38;2;{r};{g};{b}m{char}\x1b[0m"

    @classmethod
    def _visible_length(cls, value: str) -> int:
        return len(ANSI_ESCAPE_REGEX.sub("", value))


# ---------------------------------------------------------------- markdown

import re as _re
import textwrap as _textwrap
from dataclasses import dataclass as _dataclass
from typing import List as _List, Tuple as _Tuple

_HEADING_RE = _re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
_BULLET_RE = _re.compile(r"^(\s*)[-*+]\s+(.*)$")
_BOLD_RE = _re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = _re.compile(r"`([^`]+)`")
_TABLE_DIVIDER_RE = _re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_TABLE_ROW_RE = _re.compile(r"^\s*\|?.*\|?\s*$")


@_dataclass
class _MarkdownBodyTile(TerminalTileRenderable):
    markdown: str

    _owner_renderer: "Any | None" = None

    def _theme_border_rgb(self) -> Tuple[int, int, int]:
        owner = self._owner_renderer
        if owner is None:
            return (0, 180, 216)
        return TerminalSurfaceRenderer._PALETTE[owner._theme_key]

    def _palette_header_rgb(self) -> Tuple[int, int, int]:
        owner = self._owner_renderer
        if owner is None:
            return (0, 180, 216)
        return TerminalSurfaceRenderer._PALETTE[owner._theme_key]

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return "\n".join(self.render_wrapped(columns))

    def render_wrapped(self, width: int) -> _List[str]:
        width = max(width, 10)
        lines: _List[str] = []
        paragraph: _List[str] = []
        table_lines: _List[str] = []
        code_lines: _List[str] = []
        graph_verbatim_lines: _List[str] = []
        inside_code = False
        inside_table = False

        def flush_paragraph() -> None:
            if not paragraph:
                return
            text = " ".join(line.strip() for line in paragraph).strip()
            paragraph.clear()
            if not text:
                return
            text = _BOLD_RE.sub(lambda m: self._bold(m.group(1)), text)
            text = _CODE_RE.sub(lambda m: self._inline_code(m.group(1)), text)
            lines.extend(
                _textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]
            )

        def flush_table() -> None:
            if not table_lines:
                return
            rendered = self._render_table(table_lines, width)
            lines.extend(rendered)
            table_lines.clear()

        def flush_code() -> None:
            if not code_lines:
                return
            for line in code_lines:
                lines.append(line)
            code_lines.clear()

        def flush_graph_verbatim() -> None:
            """Flush a collected verbatim (GraphWidget / prefixed-space) block.

            A verbatim block is defined as a sequence of consecutive lines that
            either start with ``" "`` (one leading space) or are empty,
            interspersed with ``### Graph`` style headings that we keep.  It
            is rendered *as-is* and every produced line is left-justified to
            exactly ``width`` visible characters so the outer frame padding
            never looks "descacetado".  Crucially we do NOT run the paragraph
            textwrap on these lines because they may contain box-drawing glyphs
            (┌ ─ │ > ┐ etc.) and alignment that wraps would destroy.  This is
            used by the GraphWidget section of ``ontobdc context --graph``.
            """
            if not graph_verbatim_lines:
                return
            for raw_v in graph_verbatim_lines:
                if not raw_v.strip():
                    lines.append(" " * width)
                    continue
                # If raw_v has one leading space (GraphWidget convention),
                # strip that; caller adds frame inner breathing.
                cleaned: str = raw_v[1:] if raw_v.startswith(" ") else raw_v
                vis: int = len(ANSI_ESCAPE_REGEX.sub("", cleaned))
                if vis < width:
                    cleaned = cleaned + (" " * (width - vis))
                elif vis > width:
                    # Truncate glyphs on the right preserving ANSI escapes.
                    # Reuse the same walk used for _render_table sanity.
                    chars: _List[str] = list(cleaned)
                    out_chars: _List[str] = []
                    glyphs_remaining: int = width
                    j: int = 0
                    L: int = len(chars)
                    while j < L and glyphs_remaining > 0:
                        if chars[j] == "\x1b":
                            k: int = j
                            while k < L and chars[k] != "m":
                                k += 1
                            if k < L:
                                out_chars.extend(chars[j : k + 1])
                                j = k + 1
                            else:
                                j = L
                        else:
                            out_chars.append(chars[j])
                            glyphs_remaining -= 1
                            j += 1
                    cleaned = "".join(out_chars)
                lines.append(cleaned)
            graph_verbatim_lines.clear()

        for raw in self.markdown.splitlines():
            stripped = raw.strip()
            if stripped.startswith("```"):
                inside_table = False
                flush_paragraph()
                flush_table()
                if inside_code:
                    flush_code()
                inside_code = not inside_code
                continue
            if inside_code:
                code_lines.append(raw)
                continue

            if not stripped:
                flush_paragraph()
                flush_table()
                inside_table = False
                lines.append("")
                continue

            heading_match = _HEADING_RE.match(raw)
            if heading_match:
                flush_paragraph()
                flush_table()
                flush_graph_verbatim()
                inside_table = False
                level = len(heading_match.group(1))
                text = self._strip_inline(heading_match.group(2).strip())
                lines.append(self._format_heading(text, level, width))
                lines.append("")
                continue

            bullet_match = _BULLET_RE.match(raw)
            if bullet_match and not inside_table:
                flush_paragraph()
                flush_graph_verbatim()
                indent = len(bullet_match.group(1)) // 2
                bullet_text = self._strip_inline(bullet_match.group(2).strip())
                indent_str = "  " * indent
                bullet_w = max(1, width - len(indent_str) - 2)
                wrapped = _textwrap.wrap(bullet_text, width=bullet_w) or [""]
                lines.append(f"{indent_str}• {wrapped[0]}")
                for extra in wrapped[1:]:
                    lines.append(f"{indent_str}  {extra}")
                continue

            if _TABLE_DIVIDER_RE.match(stripped) or (inside_table and "|" in stripped):
                inside_table = True
                flush_graph_verbatim()
                table_lines.append(raw)
                continue

            if "|" in stripped and _looks_like_table_header(stripped, width):
                inside_table = True
                flush_paragraph()
                flush_graph_verbatim()
                table_lines.append(raw)
                continue

            # Verbatim / graph block: raw line starts with exactly one leading
            # space AND is not a fenced code marker (already handled above).
            # This is the GraphWidget convention in _response_to_markdown.
            if raw.startswith(" ") and not raw.startswith("  "):
                flush_paragraph()
                flush_table()
                inside_table = False
                graph_verbatim_lines.append(raw)
                continue

            # Blank lines are preserved inside verbatim blocks as blank lines,
            # otherwise they break paragraph / table / verbatim flow.
            if not stripped:
                if graph_verbatim_lines:
                    graph_verbatim_lines.append("")
                else:
                    flush_paragraph()
                    flush_table()
                    flush_graph_verbatim()
                    inside_table = False
                    lines.append("")
                continue

            inside_table = False
            flush_graph_verbatim()
            paragraph.append(raw)

        flush_paragraph()
        flush_table()
        flush_graph_verbatim()
        if inside_code:
            flush_code()
        return self._collapse(lines)

    def _format_heading(self, text: str, level: int, width: int) -> str:
        if level <= 1:
            return self._bold(text.upper()).ljust(width)
        if level == 2:
            return f"{self._bold(text)}"
        return f"  {self._bold(text)}"

    def _render_table(self, raw_table: _List[str], width: int) -> _List[str]:
        B = TerminalSurfaceRenderer._BOX
        headers: _List[str] = []
        rows: _List[_List[str]] = []
        for line in raw_table:
            if _TABLE_DIVIDER_RE.match(line.strip()):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not headers:
                headers = cells
            else:
                rows.append(cells)
        if not headers:
            return []
        col_count: int = max(
            len(headers),
            max((len(r) for r in rows), default=0),
        )
        headers = headers + [""] * (col_count - len(headers))
        normalized_rows: _List[_List[str]] = []
        for r in rows:
            normalized_rows.append(r + [""] * (col_count - len(r)))

        # -- geometry -----------------------------------------------------
        # No outer border → only the inner grid. Final visible width must
        # equal ``width`` exactly so the outer frame padding is never off.
        #
        # Rendered line = [pad][cell_0][pad][V][pad][cell_1][pad][V]...[pad][cell_{n-1}][pad]
        #               │   ── outer breathing ──    │    │  inner separators  │     ── outer breathing ──│
        inner_pad: int = 1
        n: int = len(headers)
        sep_between: int = max(0, n - 1) * (1 + 2 * inner_pad)
        outer_breathing: int = 2 * inner_pad
        grid_overhead: int = outer_breathing + sep_between
        available_cells: int = max(1, width - grid_overhead)

        # --- compute natural column widths ------------------------------
        natural_widths: _List[int] = [max(1, len(h)) for h in headers]
        for r in normalized_rows:
            for i, cell in enumerate(r):
                natural_widths[i] = max(natural_widths[i], max(1, len(cell)))

        # If everything fits exactly, great. Else: shrink the rightmost
        # columns first (longest natural), because the last descriptive
        # column is the best candidate to accept truncation while short
        # key/id columns preserve their content (matches the termimad
        # visual requested: keys right-aligned crisp, last cell wraps).
        fitted: _List[int] = list(natural_widths)
        total_natural: int = sum(fitted)
        if total_natural > available_cells:
            overflow: int = total_natural - available_cells
            shrink_order: _List[int] = sorted(
                range(n),
                key=lambda i: (-natural_widths[i], i),  # shrink biggest first
            )
            for idx in shrink_order:
                if overflow <= 0:
                    break
                can_shave: int = max(0, fitted[idx] - 3)  # min width 3
                shave: int = min(can_shave, overflow)
                if shave <= 0:
                    # fallback: shave 1 from each remaining col iteratively
                    continue
                fitted[idx] -= shave
                overflow -= shave
            # If we still overflow (all cols hit min width), do a second
            # pass removing 1 char at a time to make up the diff.
            pos: int = n - 1
            while overflow > 0 and any(fitted[i] > 3 for i in range(n)):
                if fitted[pos] > 3:
                    fitted[pos] -= 1
                    overflow -= 1
                pos = (pos - 1) % n
        elif total_natural < available_cells:
            # Expand rightmost (descriptive) column to fill the remaining
            # horizontal space so the grid always spans the full width.
            leftover: int = available_cells - total_natural
            fitted[-1] += leftover

        # --- FINAL sanity: lock the total visible width to ``width`` ----
        #
        # Neither shrink nor expand heuristics above survive every
        # round-trip (min-width floor, biggest-first proportional shares,
        # etc.).  The old code then papered over the gap by appending
        # plain whitespace AFTER the last grid separator, which made the
        # table look like it did not reach the right edge of the box —
        # the exact bug the user reported ("largura não está pegando
        # toda a largura do box").  Instead, we adjust the LAST column
        # width in BOTH directions so
        #
        #   sum(col_widths) + grid_overhead == width
        #
        # exactly.  Because the layout always leaves the last column as
        # the long descriptive one (ID / TITLE / DESCRIPTION / LOCATION),
        # absorbing a few chars there is visually invisible and keeps the
        # inner grid (┼ / │ / ─) aligned to the outer box edges.
        width_delta: int = width - (sum(fitted) + grid_overhead)
        if width_delta != 0:
            fitted[-1] = max(3, fitted[-1] + width_delta)
            # If the adjustment above somehow still misses (because the
            # last column was clamped to width 3), iteratively distribute
            # the remaining delta from right to left across any columns
            # that have room to give or take.
            second_pass_delta: int = width - (sum(fitted) + grid_overhead)
            cursor: int = n - 1
            spins: int = 0
            while second_pass_delta != 0 and spins < n:
                if second_pass_delta > 0:
                    fitted[cursor] += 1
                    second_pass_delta -= 1
                elif fitted[cursor] > 3:
                    fitted[cursor] -= 1
                    second_pass_delta += 1
                cursor = (cursor - 1) % n
                if cursor == n - 1:
                    spins += 1
        col_widths: _List[int] = fitted

        # --- alignment (user-specified): ALL body columns LEFT-aligned.
        #      Headers are UPPERCASE + CENTERED.  Right-align key-column
        #      heuristic is removed per the user's explicit "corpo tem que
        #      ser alinhado à esquerda e não à direita" request.
        alignment_body_right: _List[bool] = [False] * n

        # --- helpers -----------------------------------------------------
        header_rgb: Tuple[int, int, int] = self._palette_header_rgb()
        hr, hg, hb = header_rgb
        grid_rgb: Tuple[int, int, int] = TerminalSurfaceRenderer._PALETTE["neutral"]
        gr, gg, gb = grid_rgb
        V_GRID: str = f"\x1b[38;2;{gr};{gg};{gb}m{B['v']}\x1b[0m"
        X_GRID: str = f"\x1b[38;2;{gr};{gg};{gb}m{B['x']}\x1b[0m"
        H_GRID_OPEN: str = f"\x1b[38;2;{gr};{gg};{gb}m"
        H_GRID_CLOSE: str = "\x1b[0m"

        def _pad_cell(value: str, w: int, right: bool) -> str:
            if len(value) > w:
                value = value[: max(0, w - 1)] + "\u2026"
            value = value[:w]
            if right:
                return value.rjust(w)
            return value.ljust(w)

        def _center_cell(value: str, w: int) -> str:
            if len(value) > w:
                value = value[: max(0, w - 1)] + "\u2026"
            value = value[:w]
            total: int = w - len(value)
            left: int = total // 2
            right: int = total - left
            return (" " * left) + value + (" " * right)

        def _format_cell_plain(raw: str, i: int) -> str:
            return _pad_cell(self._strip_inline(raw), col_widths[i], alignment_body_right[i])

        def _format_cell_header(raw: str, i: int) -> str:
            text: str = _center_cell(self._strip_inline(raw).upper(), col_widths[i])
            return f"\x1b[1;38;2;{hr};{hg};{hb}m{text}\x1b[0m"

        # --- render the grid lines ---------------------------------------
        out: _List[str] = []

        # 1) Header (UPPERCASE + CENTERED + cyan bold) with grid │ in neutral
        header_segments: _List[str] = []
        for i, h in enumerate(headers):
            pad_cell: str = _format_cell_header(h, i)
            header_segments.append(" " * inner_pad + pad_cell + " " * inner_pad)

        # 2) Separator ONLY between header and body (single horizontal grid line)
        #    ─ and ┼ chars are colored neutral gray; the entire separator is
        #    wrapped in one SGR block to avoid per-char escape spam.
        sep_segs_plain: _List[str] = [B["h"] * (col_widths[i] + 2 * inner_pad) for i in range(n)]
        sep_plain: str = B["x"].join(sep_segs_plain)

        # --- BRUTAL WIDTH LOCK: make header, separator and every body line
        #     have EXACTLY ``width`` visible chars BEFORE the outer sanity runs.
        #
        #     This is the single point that guarantees the user's request
        #     ("Largura não está pegando toda a largura do box") is met even
        #     if the column-allocation math has rounding drift in a future
        #     refactor.  For header/body the gap is absorbed as EXTRA PADDING
        #     INSIDE the rightmost cell (so the last `│` vertical grid mark
        #     lands exactly on the right box edge).  For the separator the
        #     extra length is drawn as additional gray `─` characters inside
        #     the last column slot before the H_GRID_CLOSE reset.  This way
        #     the gray grid visibly extends all the way to the right frame.
        #
        #     Steps:
        #       a) compute the base visible length of what we have now.
        #       b) gap = width - base.  If gap == 0: emit as-is.
        #       c) For header / body: re-split into the (n-1) │ grid marks,
        #          take the last segment, prepend ``gap`` spaces to its LEFT
        #          (i.e. they land between the cell text content and the
        #          closing `│`), then re-join.  Because spaces land INSIDE
        #          the cell width they keep the last grid separator flush.
        #       d) For separator: insert ``gap`` extra gray `─` chars at the
        #          END of ``sep_plain`` (still inside the H_GRID_OPEN SGR) so
        #          the horizontal gray bar truly reaches the right edge.
        #
        #     Overflow (base > width) is handed to the existing truncation
        #     walk below; this block only fixes the underflow that caused
        #     "grid ends short of the box".
        def _lock_right_edge(base_line: str, *, is_separator: bool = False) -> str:
            base_vis: int = len(ANSI_ESCAPE_REGEX.sub("", base_line))
            if base_vis >= width:
                return base_line
            gap: int = width - base_vis
            if is_separator:
                # Inject gap gray dashes before the SGR reset.  H_GRID_CLOSE
                # is the literal "\x1b[0m" suffix on sep_plain output.
                if base_line.endswith(H_GRID_CLOSE):
                    return (
                        base_line[: -len(H_GRID_CLOSE)]
                        + (B["h"] * gap)
                        + H_GRID_CLOSE
                    )
                return base_line + (B["h"] * gap)

            # Header / body line: split into segments by the neutral │ V_GRID
            # literal, push gap spaces into the LAST segment so they sit
            # between the cell's last glyph and the │, inside the cell.
            if V_GRID not in base_line:
                return base_line + " " * gap
            head_rest, last_seg = base_line.rsplit(V_GRID, 1)
            return head_rest + V_GRID + (" " * gap) + last_seg

        header_line: str = V_GRID.join(header_segments)
        out.append(_lock_right_edge(header_line, is_separator=False))

        sep_line: str = f"{H_GRID_OPEN}{sep_plain}{H_GRID_CLOSE}"
        out.append(_lock_right_edge(sep_line, is_separator=True))

        # 3) Body rows (white plain, LEFT-aligned per user spec) with neutral │
        for r in normalized_rows:
            parts: _List[str] = []
            for i, cell in enumerate(r):
                text: str = _format_cell_plain(cell, i)
                parts.append(" " * inner_pad + text + " " * inner_pad)
            body_line: str = V_GRID.join(parts)
            out.append(_lock_right_edge(body_line, is_separator=False))

        # Sanity: guarantee every single line has exact visible width = width
        # so the outer frame never looks "broken / descacetado" regardless
        # of rounding at column allocation time.
        #
        # After _lock_right_edge above this block only handles OVERFLOW —
        # truncating the rightmost glyphs while keeping ANSI escapes intact.
        # We deliberately do NOT append plain trailing spaces here anymore:
        # any underflow is already absorbed inside the last cell / last
        # separator segment so the gray grid reaches the right box edge.
        final: _List[str] = []
        for line in out:
            visible: int = len(ANSI_ESCAPE_REGEX.sub("", line))
            if visible > width:
                line = line.rstrip()
                visible = len(ANSI_ESCAPE_REGEX.sub("", line))
                if visible > width:
                    chars: _List[str] = list(line)
                    out_chars: _List[str] = []
                    glyphs_remaining: int = width
                    j: int = 0
                    L: int = len(chars)
                    while j < L and glyphs_remaining > 0:
                        if chars[j] == "\x1b":
                            k: int = j
                            while k < L and chars[k] != "m":
                                k += 1
                            if k < L:
                                out_chars.extend(chars[j : k + 1])
                                j = k + 1
                            else:
                                j = L
                        else:
                            out_chars.append(chars[j])
                            glyphs_remaining -= 1
                            j += 1
                    line = "".join(out_chars)
            final.append(line)

        return final

    def _frame_table_row(self, row: str, widths: _List[int]) -> str:
        _ = widths
        return row

    def _theme_border(self, text: str) -> str:
        r, g, b = TerminalSurfaceRenderer._PALETTE["neutral"]
        return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"

    def _bold(self, text: str) -> str:
        return f"\x1b[1m{text}\x1b[0m"

    def _inline_code(self, text: str) -> str:
        return f"\x1b[38;2;220;220;220;48;2;40;40;40m{text}\x1b[0m"

    def _strip_inline(self, text: str) -> str:
        return _BOLD_RE.sub(r"\1", _CODE_RE.sub(r"\1", text)).strip()

    @staticmethod
    def _collapse(lines: _List[str]) -> _List[str]:
        out: _List[str] = []
        prev_blank = False
        for line in lines:
            blank = line == ""
            if blank and prev_blank:
                continue
            out.append(line)
            prev_blank = blank
        while out and out[-1] == "":
            out.pop()
        return out


def _looks_like_table_header(stripped: str, width: int) -> bool:
    _ = width
    if "|" not in stripped:
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cells) < 2:
        return False
    return True


def _make_markdown_body_tile(markdown: str) -> type:
    md: str = markdown

    class _DynamicMarkdownTile(TerminalTileRenderable):
        def render(
            self_self,
            *,
            columns: int,
            rows: int,
            context: Optional[Dict[str, Any]] = None,
        ) -> str:
            tile = _MarkdownBodyTile(markdown=md)
            return tile.render(columns=columns, rows=rows, context=context)

    return _DynamicMarkdownTile
