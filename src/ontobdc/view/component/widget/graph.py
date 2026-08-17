from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from rich.console import Console

from ontobdc.view.domain.port.widget import Widget


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str

    def __str__(self) -> str:
        return self.label


BOX_CHARS: Dict[str, str] = {
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
}


def _truncate_right(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "\u2026"
    return text[: width - 1] + "\u2026"


def _node_box(label: str, max_label_width: int, *, inner_pad: int = 1) -> Tuple[str, str, str, int]:
    padded = (" " * inner_pad) + _truncate_right(label, max_label_width).ljust(max_label_width) + (" " * inner_pad)
    inner_width: int = len(padded)
    top = BOX_CHARS["tl"] + BOX_CHARS["h"] * inner_width + BOX_CHARS["tr"]
    mid = BOX_CHARS["v"] + padded + BOX_CHARS["v"]
    bot = BOX_CHARS["bl"] + BOX_CHARS["h"] * inner_width + BOX_CHARS["br"]
    return top, mid, bot, len(top)


def _build_arrow(src_width: int, total: int, tgt_width: int) -> str:
    between: int = total - src_width - tgt_width
    if between <= 2:
        return " " + ">" + " " * max(0, between - 2)
    dash_count: int = between - 2
    return " " + BOX_CHARS["h"] * dash_count + ">" + " "


def _center_under(text: str, total: int, *, start_col: int) -> str:
    text_trim: str = text
    width: int = len(text_trim)
    left_pad: int = start_col
    line: str = " " * left_pad + text_trim
    if len(line) < total:
        line += " " * (total - len(line))
    return line[:total]


@dataclass
class GraphWidget(Widget):
    """Render a node/edge graph as a terminal-friendly deterministic left-to-right layout.

    The previous implementation relied on ``netext``'s ``ConsoleGraph`` with a
    force-directed or sugiyama layout.  Although a ``width`` parameter was
    passed to the ``rich.console.Console`` constructor, the resulting layout
    (especially after ``zoom=AutoZoom.FIT_PROPORTIONAL``) was still allowed to
    overshoot the requested column count for nodes/labels on wide graphs, so
    boxes wrapped, edge segments became orphaned and the rendering looked
    "descacetado" on commands such as ``ontobdc context --graph``.

    This new renderer:

    * is fully width-bounded: every produced line is exactly
      ``available_columns`` wide (or narrower, then space-padded to that width)
    * draws every edge as a deterministic 4-row block::

          ┌─ source box ─┐      ──────>    ┌─ target box ─┐
          │ "source label │                │ target label │
          └───────────────┘                └──────────────┘
                             obdc:context/1

    * truncates node and edge labels on the right with an ellipsis when they
      exceed their respective maxima (so a single URI/IRI label never pushes a
      whole block beyond the right terminal frame).
    """

    nodes: List[Dict[str, str]] = field(default_factory=list)
    edges: List[Dict[str, str]] = field(default_factory=list)
    layout: str = "force"
    orientation: str = "default"

    node_label_max_w: int = 50
    edge_label_max_w: int = 40

    def render(self, available_columns: int) -> List[str]:
        if not self.nodes:
            return []

        total_w: int = max(available_columns, 60)

        node_map: Dict[str, str] = {}
        for n in self.nodes:
            nid = str(n.get("id", ""))
            node_map[nid] = str(n.get("label", nid))

        max_natural_label: int = max((len(lbl) for lbl in node_map.values()), default=8)
        # Limit label width so two boxes + an arrow + whitespace always fits total_w
        # Geometric budget for a single edge row:
        # src_box + between_whitespace + tgt_box
        # Label max is bounded so two boxes of same width never exceed ~60% of width.
        hard_cap: int = max(10, (total_w - 16) // 2 - 2)
        label_w: int = max(10, min(self.node_label_max_w, max_natural_label, hard_cap))

        # Dedup edges
        seen: set[Tuple[str, str, str]] = set()
        edge_list: List[Tuple[str, str, str]] = []
        for e in self.edges:
            src: str = str(e.get("source", ""))
            tgt: str = str(e.get("target", ""))
            lbl: str = str(e.get("label", ""))
            if not src or not tgt:
                continue
            if src not in node_map or tgt not in node_map:
                continue
            k: Tuple[str, str, str] = (src, tgt, lbl)
            if k in seen:
                continue
            seen.add(k)
            edge_list.append(k)

        output: List[str] = []
        for idx, (src_id, tgt_id, edge_label) in enumerate(edge_list):
            src_t, src_m, src_b, src_w = _node_box(node_map[src_id], label_w)
            tgt_t, tgt_m, tgt_b, tgt_w = _node_box(node_map[tgt_id], label_w)

            # Top row: src_top + spaces + tgt_top
            between_top: int = total_w - src_w - tgt_w
            if between_top < 0:
                # shrink label_w on the right (truncate target more) — fallback
                new_tgt_label_w: int = max(8, label_w + between_top - 2)
                tgt_t, tgt_m, tgt_b, tgt_w = _node_box(node_map[tgt_id], new_tgt_label_w)
                between_top = total_w - src_w - tgt_w
            between_top = max(0, between_top)
            top_row: str = src_t + (" " * between_top) + tgt_t
            if len(top_row) < total_w:
                top_row += " " * (total_w - len(top_row))

            # Mid row: src_mid + " " + ────> + " "*(leftover) + tgt_mid
            between_mid: int = total_w - src_w - tgt_w
            between_mid = max(0, between_mid)
            arrow: str = _build_arrow(src_w, total_w, tgt_w)
            # Replace exactly `between_mid` chars with the arrow string padded
            arrow_len: int = len(arrow)
            if arrow_len < between_mid:
                mid_between: str = arrow + (" " * (between_mid - arrow_len))
            elif arrow_len > between_mid:
                mid_between: str = arrow[:between_mid]
            else:
                mid_between: str = arrow
            mid_row: str = src_m + mid_between + tgt_m

            # Bottom row: src_b + spaces + tgt_b
            between_bot: int = max(0, total_w - src_w - tgt_w)
            bot_row: str = src_b + (" " * between_bot) + tgt_b
            if len(bot_row) < total_w:
                bot_row += " " * (total_w - len(bot_row))

            # Lock widths: guarantee exact total_w visible columns
            for row in (top_row, mid_row, bot_row):
                if len(row) > total_w:
                    row = row[:total_w]
                elif len(row) < total_w:
                    row = row + " " * (total_w - len(row))

            output.append(top_row[:total_w])
            output.append(mid_row[:total_w])
            output.append(bot_row[:total_w])

            # Edge label row (under the arrow, left-aligned so long labels still start where the arrow began)
            if edge_label:
                label_trunc: str = _truncate_right(edge_label, self.edge_label_max_w)
                # Align to ~center of the arrow: arrow starts at column src_w
                label_start_col: int = src_w + max(0, (total_w - src_w - tgt_w) // 2 - len(label_trunc) // 2)
                label_start_col = max(src_w, label_start_col)
                label_row: str = _center_under(label_trunc, total_w, start_col=label_start_col)
                if len(label_row) < total_w:
                    label_row += " " * (total_w - len(label_row))
                output.append(label_row[:total_w])

            # blank separator row between edges (but not at the very end)
            if idx != len(edge_list) - 1:
                output.append(" " * total_w)

        # If somehow produced rows are longer/shorter than total_w, re-pad here
        final: List[str] = []
        for line in output:
            if len(line) > total_w:
                final.append(line[:total_w])
            elif len(line) < total_w:
                final.append(line + " " * (total_w - len(line)))
            else:
                final.append(line)
        return final


# Also expose the legacy helpers for other modules that may have used them (none)
__all__ = ["GraphWidget", "GraphNode"]
