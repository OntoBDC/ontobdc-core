import re
import textwrap
from typing import Any, ClassVar, Dict, FrozenSet, List, Optional, Pattern, Tuple

from ontobdc.shared.adapter.surface.box import SurfaceBox
from ontobdc.shared.adapter.terminal_text import TerminalTextMetrics
from ontobdc.shared.adapter.terminal_color import TerminalColor
from ontobdc.shared.adapter.surface.palette import SurfacePalette
from ontobdc.shared.domain.port.component import TerminalTileRenderable


class MarkdownBodyTile(TerminalTileRenderable):
    """
    Terminal tile that renders a markdown body inside a surface region.

    The tile owns the markdown it renders and the theme it paints with, so
    it needs no back-reference to the renderer that frames it.
    """
    _HEADING_RE: ClassVar[Pattern[str]] = re.compile(
        r"^(?P<prefix>.*?)(?<!\\)(#{1,6})\s+(.*)$"
    )
    # "\u2022" is matched alongside the plain markdown markers because
    # TextWidget.render() already converts "- item" lines into "\u2022 item"
    # before handing its output back through this same markdown pipeline.
    # Without it, those already-bulleted lines would be unrecognised, plain
    # paragraph text and would get merged onto a single line by the
    # paragraph flusher below.
    _BULLET_RE: ClassVar[Pattern[str]] = re.compile(r"^(\s*)[-*+\u2022]\s+(.*)$")
    _BULLET_LABEL_RE: ClassVar[Pattern[str]] = re.compile(r"^([A-Z][A-Z0-9 _-]*):\s(.*)$")
    _BOLD_RE: ClassVar[Pattern[str]] = re.compile(r"\*\*(.+?)\*\*")
    _CODE_RE: ClassVar[Pattern[str]] = re.compile(r"`([^`]+)`")
    _TABLE_DIVIDER_RE: ClassVar[Pattern[str]] = re.compile(
        r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
    )

    # A body cell whose entire text is one of these status words is tinted
    # so a pass/fail column reads at a glance.
    _STATUS_CELL_COLORS: ClassVar[Dict[str, str]] = {
        "pass": TerminalColor.GREEN,
        "passed": TerminalColor.GREEN,
        "ok": TerminalColor.GREEN,
        "healthy": TerminalColor.GREEN,
        "success": TerminalColor.GREEN,
        "fail": TerminalColor.RED,
        "failed": TerminalColor.RED,
        "error": TerminalColor.RED,
        "unhealthy": TerminalColor.RED,
    }
    # A "LABEL: value" bullet whose label is one of these renders its value
    # dimmed: it is a machine reference, not something read word by word.
    _DIM_VALUE_BULLET_LABELS: ClassVar[FrozenSet[str]] = frozenset({"URI", "IRI", "URN"})

    def __init__(self, markdown: str, theme: str = SurfacePalette.DEFAULT_THEME) -> None:
        self.markdown: str = markdown
        self._theme_key: str = SurfacePalette.normalize(theme)

    def _palette_header_rgb(self) -> Tuple[int, int, int]:
        return SurfacePalette.rgb_for(self._theme_key)

    def render(
        self,
        *,
        columns: int,
        rows: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        return "\n".join(self.render_wrapped(columns))

    def render_wrapped(self, width: int) -> List[str]:
        width = max(width, 10)
        lines: List[str] = []
        paragraph: List[str] = []
        table_lines: List[str] = []
        code_lines: List[str] = []
        graph_verbatim_lines: List[str] = []
        inside_code = False
        inside_table = False

        def flush_paragraph() -> None:
            if not paragraph:
                return
            text = " ".join(line.strip() for line in paragraph).strip()
            paragraph.clear()
            if not text:
                return
            text = self._BOLD_RE.sub(lambda m: self._bold(m.group(1)), text)
            text = self._CODE_RE.sub(lambda m: self._inline_code(m.group(1)), text)
            lines.extend(
                textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [""]
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
                vis: int = TerminalTextMetrics.width_of(TerminalColor.ANSI_ESCAPE_REGEX.sub("", cleaned))
                if vis < width:
                    cleaned = cleaned + (" " * (width - vis))
                elif vis > width:
                    # Truncate glyphs on the right preserving ANSI escapes,
                    # spending 2 columns of budget per wide/emoji glyph so a
                    # double-width character never gets counted as if it
                    # only occupied one. Reuse the same walk used for
                    # _render_table sanity.
                    chars: List[str] = list(cleaned)
                    out_chars: List[str] = []
                    glyphs_remaining: int = width
                    j: int = 0
                    L: int = len(chars)
                    while j < L and glyphs_remaining > 0:
                        if chars[j] == TerminalColor.CSI[0] and "".join(chars[j:j+len(TerminalColor.CSI)]) == TerminalColor.CSI:
                            k: int = j
                            while k < L and chars[k] != "m":
                                k += 1
                            if k < L:
                                out_chars.extend(chars[j : k + 1])
                                j = k + 1
                            else:
                                j = L
                        else:
                            char_width: int = TerminalTextMetrics.character_width(chars[j])
                            if char_width > glyphs_remaining:
                                break
                            out_chars.append(chars[j])
                            glyphs_remaining -= char_width
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
                # A blank line inside an accumulating verbatim block (see
                # the "starts with exactly one leading space" branch below)
                # must be preserved *inside* that block instead of flushed
                # here as a generic paragraph separator — otherwise a
                # widget like TreeWidget that emits an intentional blank
                # row (e.g. between a "Datasets" section and the next
                # top-level branch) loses it, because this check used to
                # run unconditionally before the verbatim-aware one further
                # below ever got a chance to see it.
                if graph_verbatim_lines:
                    graph_verbatim_lines.append("")
                elif raw:
                    flush_paragraph()
                    flush_table()
                    inside_table = False
                    lines.append(" ")
                else:
                    flush_paragraph()
                    flush_table()
                    flush_graph_verbatim()
                    inside_table = False
                    lines.append("")
                continue

            heading_match = self._HEADING_RE.match(raw)
            if heading_match:
                flush_paragraph()
                flush_table()
                flush_graph_verbatim()
                inside_table = False
                prefix: str = heading_match.group("prefix") or ""
                level = len(heading_match.group(2))
                text = self._strip_inline(heading_match.group(3).strip())
                hr, hg, hb = SurfacePalette.rgb_for(self._theme_key)
                if level <= 1:
                    heading_body: str = text.upper()
                    styled_heading: str = (
                        f"{TerminalColor.BOLD}{TerminalColor.rgb_fg_bold(hr, hg, hb)}{heading_body}{TerminalColor.RESET}"
                    )
                elif level == 2:
                    heading_body = text.upper()
                    styled_pipe: str = f"{TerminalColor.rgb_bg(hr, hg, hb)} {TerminalColor.RESET} "
                    styled_heading = (
                        f"{styled_pipe}{TerminalColor.BOLD}{TerminalColor.rgb_fg_bold(hr, hg, hb)}{heading_body}{TerminalColor.RESET}"
                    )
                elif level == 3:
                    heading_body = text
                    styled_pipe = f"{TerminalColor.rgb_bg(hr, hg, hb)} {TerminalColor.RESET} "
                    styled_heading = (
                        f"  {styled_pipe}{TerminalColor.BOLD}{TerminalColor.rgb_fg_bold(hr, hg, hb)}{heading_body}{TerminalColor.RESET}"
                    )
                else:
                    # level >= 4 → per-record card title (e.g. the DETAILS
                    # section). Same indent as level 3, but a colored "_"
                    # marker instead of a solid background block — a filled
                    # square per card reads noisy when there are many rows.
                    heading_body = text
                    styled_marker = f"{TerminalColor.rgb_fg(hr, hg, hb)}_{TerminalColor.RESET} "
                    styled_heading = (
                        f"  {styled_marker}{TerminalColor.BOLD}{TerminalColor.rgb_fg_bold(hr, hg, hb)}{heading_body}{TerminalColor.RESET}"
                    )
                lines.append(f"{prefix}{styled_heading}")
                lines.append("")
                continue

            # Detail line: a raw line prefixed with a literal tab is a
            # dimmed, indented sub-line attached to the bullet/paragraph
            # above it (e.g. the "Example: ..." line under a "Commands"
            # entry -- see ``CommandResponseRenderer.response_to_markdown`` in ``cli/__init__.py``).
            # It is flushed on its own, never merged into a paragraph, and
            # never mistaken for a markdown table header even if its text
            # contains "|" (a joined usage example). Tab is otherwise unused
            # by any markdown this renderer produces, so this cannot collide
            # with heading/bullet/table detection above.
            if raw.startswith("\t"):
                flush_paragraph()
                flush_graph_verbatim()
                detail_text: str = raw[1:]
                detail_indent: str = "  "
                available: int = max(1, width - len(detail_indent))
                visible: int = TerminalTextMetrics.width_of(TerminalColor.ANSI_ESCAPE_REGEX.sub("", detail_text))
                if visible > available:
                    detail_text = TerminalTextMetrics.truncate_visible(
                        detail_text, available
                    )
                lines.append(f"{detail_indent}{detail_text}")
                continue

            bullet_match = self._BULLET_RE.match(raw)
            if bullet_match and not inside_table:
                flush_paragraph()
                flush_graph_verbatim()
                indent = len(bullet_match.group(1)) // 2
                bullet_text = self._strip_inline(bullet_match.group(2).strip())
                indent_str = "  " * indent

                # "LABEL: value" bullets (e.g. the DETAILS cards) get their
                # bullet glyph and label styled in the theme accent color,
                # matching the table headers; the value stays plain. Bullets
                # that don't follow that shape render exactly as before.
                br, bg_, bb = self._palette_header_rgb()
                label_match = self._BULLET_LABEL_RE.match(bullet_text)
                label_prefix: str = ""
                body_text: str = bullet_text
                dim_value: bool = False
                if label_match:
                    label_prefix = f"{label_match.group(1)}: "
                    body_text = label_match.group(2)
                    dim_value = (
                        label_match.group(1).upper()
                        in self._DIM_VALUE_BULLET_LABELS
                    )

                bullet_w = max(1, width - len(indent_str) - 2 - len(label_prefix))
                wrapped = textwrap.wrap(body_text, width=bullet_w) or [""]
                if dim_value:
                    wrapped = [f"{TerminalColor.GRAY}{piece}{TerminalColor.RESET}" for piece in wrapped]

                styled_bullet: str = f"{TerminalColor.rgb_fg_bold(br, bg_, bb)}•{TerminalColor.RESET}"
                styled_label: str = (
                    f"{TerminalColor.BOLD}{TerminalColor.rgb_fg_bold(br, bg_, bb)}{label_prefix}{TerminalColor.RESET}"
                    if label_prefix
                    else ""
                )
                continuation_indent: str = " " * len(label_prefix)

                lines.append(f"{indent_str}{styled_bullet} {styled_label}{wrapped[0]}")
                for extra in wrapped[1:]:
                    lines.append(f"{indent_str}  {continuation_indent}{extra}")
                continue

            if self._TABLE_DIVIDER_RE.match(stripped) or (inside_table and "|" in stripped):
                inside_table = True
                flush_graph_verbatim()
                table_lines.append(raw)
                continue

            if "|" in stripped and self._looks_like_table_header(stripped, width):
                inside_table = True
                flush_paragraph()
                flush_graph_verbatim()
                table_lines.append(raw)
                continue

            # Verbatim / graph block: raw line starts with exactly one leading
            # space AND is not a fenced code marker (already handled above).
            # This is the GraphWidget convention in CommandResponseRenderer.response_to_markdown.
            if raw.startswith(" ") and not raw.startswith("  "):
                flush_paragraph()
                flush_table()
                inside_table = False
                graph_verbatim_lines.append(raw)
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

    def _render_table(self, raw_table: List[str], width: int) -> List[str]:
        B = SurfaceBox.CHARS
        headers: List[str] = []
        rows: List[List[str]] = []
        for line in raw_table:
            if self._TABLE_DIVIDER_RE.match(line.strip()):
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
        normalized_rows: List[List[str]] = []
        for r in rows:
            normalized_rows.append(r + [""] * (col_count - len(r)))

        # -- geometry -----------------------------------------------------
        # No outer border → only the inner grid.
        #
        # Rendered line = [pad][cell_0][pad][V][pad][cell_1][pad][V]...[pad][cell_{n-1}][pad]
        #               │   ── outer breathing ──    │    │  inner separators  │     ── outer breathing ──│
        inner_pad: int = 1

        # --- compute natural column widths ------------------------------
        natural_widths: List[int] = [max(1, len(h)) for h in headers]
        for r in normalized_rows:
            for i, cell in enumerate(r):
                natural_widths[i] = max(natural_widths[i], max(1, len(cell)))

        # Keep only as many columns as fit the box, left to right, instead
        # of squeezing every column onto the screen. Each included column
        # gets its natural (untruncated) width — never stretched wider than
        # that just to burn up leftover space — and body text within it may
        # still wrap onto extra lines. The moment the next column would no
        # longer fit at its natural width, scanning stops and that column
        # (and any further ones) is simply left out of the table; every
        # field still appears in full under the DETAILS cards rendered
        # below (see ``CommandResponseRenderer.response_to_markdown`` in ``cli/__init__.py``), so
        # nothing is lost, only not repeated in the compact table.
        _FORCED_COL_FLOOR: int = 10
        natural_fit_idx: List[int] = []
        running_width: int = 0
        for i in range(len(headers)):
            col_count: int = len(natural_fit_idx) + 1
            trial_overhead: int = 2 * inner_pad + max(0, col_count - 1) * (1 + 2 * inner_pad)
            trial_avail: int = width - trial_overhead
            trial_total: int = running_width + natural_widths[i]
            if trial_total > trial_avail:
                break
            natural_fit_idx.append(i)
            running_width = trial_total

        if len(natural_fit_idx) >= 2 or len(natural_fit_idx) == len(headers):
            included_idx: List[int] = natural_fit_idx
            fitted: List[int] = [natural_widths[i] for i in included_idx]
        elif len(headers) >= 2:
            # Only the 1st column fit naturally, but at least 2 columns are
            # kept when 2+ are available. Rather than starving the 2nd
            # column down to an unreadable sliver (which, wrapped, could
            # balloon into dozens of near-empty lines), split the box
            # between exactly these first 2 columns proportionally to their
            # natural sizes, each floored at a still-legible width.
            overhead2: int = 2 * inner_pad + (1 + 2 * inner_pad)
            avail2: int = max(2 * _FORCED_COL_FLOOR, width - overhead2)
            w0, w1 = natural_widths[0], natural_widths[1]
            total2: int = w0 + w1
            if total2 <= avail2:
                fitted = [w0, w1]
            else:
                shrinkable0: int = max(0, w0 - _FORCED_COL_FLOOR)
                shrinkable1: int = max(0, w1 - _FORCED_COL_FLOOR)
                total_shrinkable: int = shrinkable0 + shrinkable1
                if total_shrinkable <= 0:
                    fitted = [_FORCED_COL_FLOOR, _FORCED_COL_FLOOR]
                else:
                    to_shave: int = min(total2 - avail2, total_shrinkable)
                    shave0: int = round(to_shave * shrinkable0 / total_shrinkable)
                    shave1: int = to_shave - shave0
                    fitted = [max(_FORCED_COL_FLOOR, w0 - shave0), max(_FORCED_COL_FLOOR, w1 - shave1)]
            included_idx = [0, 1]
        else:
            included_idx = [0]
            fitted = [natural_widths[0]]

        headers = [headers[i] for i in included_idx]
        normalized_rows = [[r[i] for i in included_idx] for r in normalized_rows]
        n: int = len(headers)
        col_widths: List[int] = fitted

        # --- alignment (user-specified): ALL body columns LEFT-aligned.
        #      Headers are UPPERCASE + CENTERED.  Right-align key-column
        #      heuristic is removed per the user's explicit "corpo tem que
        #      ser alinhado à esquerda e não à direita" request.
        # --- helpers -----------------------------------------------------
        header_rgb: Tuple[int, int, int] = self._palette_header_rgb()
        hr, hg, hb = header_rgb
        grid_rgb: Tuple[int, int, int] = SurfacePalette.rgb_for("neutral")
        gr, gg, gb = grid_rgb
        V_GRID: str = f"{TerminalColor.rgb_fg(gr, gg, gb)}{B['v']}{TerminalColor.RESET}"
        X_GRID: str = f"{TerminalColor.rgb_fg(gr, gg, gb)}{B['x']}{TerminalColor.RESET}"
        H_GRID_OPEN: str = TerminalColor.rgb_fg(gr, gg, gb)
        H_GRID_CLOSE: str = TerminalColor.RESET

        def _center_cell(value: str, w: int) -> str:
            # Headers fit their column's natural width by construction,
            # except a 2nd column forced below it to the small floor (see
            # ``_FORCED_COL_FLOOR`` above) — this truncation only bites in
            # that narrow edge case.
            if len(value) > w:
                value = value[: max(0, w - 1)] + "\u2026"
            value = value[:w]
            total: int = w - len(value)
            left: int = total // 2
            right: int = total - left
            return (" " * left) + value + (" " * right)

        def _wrap_cell(raw: str, w: int) -> List[str]:
            """Word-wrap a body cell to width ``w`` -- never truncates: long
            unbroken tokens (e.g. URNs) are hard-broken instead of cut."""
            plain: str = self._strip_inline(raw)
            wrapped: List[str] = textwrap.wrap(
                plain, width=max(1, w), break_long_words=True, break_on_hyphens=False
            )
            return wrapped or [""]

        def _format_cell_header(raw: str, i: int) -> str:
            text: str = _center_cell(self._strip_inline(raw).upper(), col_widths[i])
            return f"{TerminalColor.rgb_fg_bold(hr, hg, hb)}{text}{TerminalColor.RESET}"

        # --- render the grid lines ---------------------------------------
        out: List[str] = []

        # 1) Header (UPPERCASE + CENTERED + cyan bold) with grid │ in neutral
        header_segments: List[str] = []
        for i, h in enumerate(headers):
            pad_cell: str = _format_cell_header(h, i)
            header_segments.append(" " * inner_pad + pad_cell + " " * inner_pad)

        # 2) Separator ONLY between header and body (single horizontal grid line)
        #    ─ and ┼ chars are colored neutral gray; the entire separator is
        #    wrapped in one SGR block to avoid per-char escape spam.
        sep_segs_plain: List[str] = [B["h"] * (col_widths[i] + 2 * inner_pad) for i in range(n)]
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
        #       c) For header / body: append ``gap`` trailing spaces. The
        #          rightmost cell is centred (header) or left-aligned
        #          (body) within its own natural width, so the slack sits
        #          to its right, not shoved in front of its text.
        #       d) For separator: insert ``gap`` extra gray `─` chars at the
        #          END of ``sep_plain`` (still inside the H_GRID_OPEN SGR) so
        #          the horizontal gray bar truly reaches the right edge.
        #
        #     Overflow (base > width) is handed to the existing truncation
        #     walk below; this block only fixes the underflow that caused
        #     "grid ends short of the box".
        def _lock_right_edge(base_line: str, *, is_separator: bool = False) -> str:
            base_vis: int = len(TerminalColor.ANSI_ESCAPE_REGEX.sub("", base_line))
            if base_vis >= width:
                return base_line
            gap: int = width - base_vis
            if is_separator:
                # Inject gap gray dashes before the SGR reset.  H_GRID_CLOSE
                # is the SGR reset (TerminalColor.RESET) suffix on sep_plain output.
                if base_line.endswith(H_GRID_CLOSE):
                    return (
                        base_line[: -len(H_GRID_CLOSE)]
                        + (B["h"] * gap)
                        + H_GRID_CLOSE
                    )
                return base_line + (B["h"] * gap)

            # Header / body line: the leftover width is trailing space on
            # the rightmost cell. Headers are centred and body cells are
            # left-aligned within their natural column width, so the gap
            # belongs *after* that content -- prepending it instead shoved
            # a narrow last column's header (e.g. an all-empty "DETAIL")
            # to the far right of the frame.
            return base_line + " " * gap

        header_line: str = V_GRID.join(header_segments)
        out.append(_lock_right_edge(header_line, is_separator=False))

        sep_line: str = f"{H_GRID_OPEN}{sep_plain}{H_GRID_CLOSE}"
        out.append(_lock_right_edge(sep_line, is_separator=True))

        # 3) Body rows (white plain, LEFT-aligned per user spec) with neutral │.
        #    Each cell is word-wrapped to its column width instead of
        #    truncated — a row that doesn't fit on one line grows extra
        #    physical lines instead of losing characters.
        for r in normalized_rows:
            wrapped_cells: List[List[str]] = [
                _wrap_cell(cell, col_widths[i]) for i, cell in enumerate(r)
            ]
            row_height: int = max(1, max(len(wc) for wc in wrapped_cells))
            status_color: Dict[int, str] = {
                i: self._STATUS_CELL_COLORS[
                    self._strip_inline("".join(wc)).strip().lower()
                ]
                for i, wc in enumerate(wrapped_cells)
                if self._strip_inline("".join(wc)).strip().lower()
                in self._STATUS_CELL_COLORS
            }
            for line_idx in range(row_height):
                parts: List[str] = []
                for i in range(n):
                    cell_lines: List[str] = wrapped_cells[i]
                    text: str = cell_lines[line_idx] if line_idx < len(cell_lines) else ""
                    cell: str = text.ljust(col_widths[i])
                    if i in status_color:
                        # Tint after ljust so the padding is inside the SGR
                        # run; _visible_length / _lock_right_edge strip ANSI
                        # before measuring, so width math is unaffected.
                        cell = f"{status_color[i]}{cell}{TerminalColor.RESET}"
                    parts.append(" " * inner_pad + cell + " " * inner_pad)
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
        final: List[str] = []
        for line in out:
            visible: int = len(TerminalColor.ANSI_ESCAPE_REGEX.sub("", line))
            if visible > width:
                line = line.rstrip()
                visible = len(TerminalColor.ANSI_ESCAPE_REGEX.sub("", line))
                if visible > width:
                    chars: List[str] = list(line)
                    out_chars: List[str] = []
                    glyphs_remaining: int = width
                    j: int = 0
                    L: int = len(chars)
                    while j < L and glyphs_remaining > 0:
                        if chars[j] == TerminalColor.CSI[0] and "".join(chars[j:j+len(TerminalColor.CSI)]) == TerminalColor.CSI:
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

    def _bold(self, text: str) -> str:
        return f"{TerminalColor.BOLD}{text}{TerminalColor.RESET}"

    def _inline_code(self, text: str) -> str:
        return f"{TerminalColor.rgb_fg(220, 220, 220)}{TerminalColor.rgb_bg(40, 40, 40)}{text}{TerminalColor.RESET}"

    def _strip_inline(self, text: str) -> str:
        return self._BOLD_RE.sub(r"\1", self._CODE_RE.sub(r"\1", text)).strip()

    @staticmethod
    def _collapse(lines: List[str]) -> List[str]:
        out: List[str] = []
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

    @staticmethod
    def _looks_like_table_header(stripped: str, width: int) -> bool:
        _ = width
        if "|" not in stripped:
            return False
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            return False
        return True
