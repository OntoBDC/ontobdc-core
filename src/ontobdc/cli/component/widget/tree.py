from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

from ontobdc.cli.domain.port.widget import Widget

_ICONS: Dict[str, str] = {
    "root": "📦",
    "section": "📌",
    "dataset": "🗂",
    "dir": "📁",
    "file": "📄",
    "config": "⚙️",
    "entity": "◆",
    "time": "⏳",
    "drawing": "📐",
    "model": "🧊",
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
                extension: str = "    " if is_last else "│   "
                self._render_children(children, prefix + extension, lines)
                breathing_kinds: Tuple[str, ...] = (
                    "section",
                    "model",
                    "drawing",
                )
                if (
                    not prefix
                    and not is_last
                    and str(node.get("kind") or "") in breathing_kinds
                ):
                    lines.append(f"{prefix}│")

    @staticmethod
    def _fit(line: str, width: int) -> str:
        if len(line) > width:
            return line[: max(0, width - 1)] + "…"
        return line
