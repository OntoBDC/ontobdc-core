from dataclasses import dataclass, field
from typing import Any, Dict, List

from ontobdc.view.domain.port.widget import Widget

_ICONS: Dict[str, str] = {
    "root": "📦",
    "section": "📌",
    "dataset": "🗂",
    "dir": "📁",
    "file": "📄",
}


@dataclass
class TreeWidget(Widget):
    """Render a nested ``{name, kind, children}`` node as a directory-tree
    diagram — guide lines and branch glyphs in the same visual family as
    https://textual.textualize.io/widgets/directory_tree/ — using this
    app's own box-drawing character set so it reads consistently with the
    rest of the boxed terminal UI.
    """

    root: Dict[str, Any] = field(default_factory=dict)

    def render(self, available_columns: int) -> List[str]:
        width: int = max(available_columns, 20)
        if not self.root:
            return []

        lines: List[str] = []
        root_icon: str = _ICONS.get(str(self.root.get("kind") or "root"), "")
        root_name: str = str(self.root.get("name") or "")
        lines.append(f"{root_icon}  {root_name}".strip())
        self._render_children(self.root.get("children") or [], "", lines)
        return [self._fit(line, width) for line in lines]

    def _render_children(
        self,
        nodes: List[Dict[str, Any]],
        prefix: str,
        lines: List[str],
    ) -> None:
        total: int = len(nodes)
        for index, node in enumerate(nodes):
            is_last: bool = index == total - 1
            branch: str = "└── " if is_last else "├── "
            icon: str = _ICONS.get(str(node.get("kind") or "file"), "")
            name: str = str(node.get("name") or "")
            label: str = f"{icon}  {name}" if icon else name
            lines.append(f"{prefix}{branch}{label}".rstrip())
            children: List[Dict[str, Any]] = node.get("children") or []
            if children:
                # NBSP (not a plain space) for the blank continuation run:
                # the CLI's markdown-to-terminal pass only treats a line as
                # pre-formatted "verbatim" (not reflowed) when it starts
                # with *exactly one* leading plain space. A deeply nested
                # branch whose every ancestor was the last sibling would
                # otherwise accumulate multiple leading plain spaces here
                # and get mistaken for an ordinary paragraph and rewrapped,
                # destroying the tree's indentation.
                extension: str = "    " if is_last else "│   "
                self._render_children(children, prefix + extension, lines)
                # A labeled top-level group (e.g. "Datasets") gets one
                # breathing blank line after its own subtree, so it doesn't
                # run straight into the next top-level branch.
                if (
                    not prefix
                    and not is_last
                    and str(node.get("kind") or "") == "section"
                ):
                    lines.append("")

    @staticmethod
    def _fit(line: str, width: int) -> str:
        if len(line) > width:
            return line[: max(0, width - 1)] + "…"
        return line
