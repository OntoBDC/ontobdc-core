from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Label, Tree
from textual.widgets.tree import TreeNode

from ontobdc.context.adapter.suggestion_tree import (
    SuggestionCategoryEntry,
    SuggestionFileEntry,
    SuggestionStructuredData,
)


SCORE_COLOR_GREEN: str = "#2ecc71"
SCORE_COLOR_BLUE: str = "#3498db"
SCORE_COLOR_WHITE: str = "#f4fbfd"
SCORE_COLOR_GRAY: str = "#7f8c8d"


@dataclass(frozen=True)
class SuggestionApprovalResult:
    selected_categories: Tuple[str, ...]
    selected_files_by_category: Tuple[Tuple[str, Tuple[str, ...]], ...]


class SuggestionApprovalApp(App[Optional[SuggestionApprovalResult]]):
    TITLE: ClassVar[str] = "OntoBDC"
    SUB_TITLE: ClassVar[str] = "Context Suggestion Approval"
    CSS: ClassVar[str] = """
    Screen {
        background: #071820;
        color: #f4fbfd;
    }

    Header {
        background: #00b4d8;
        color: #001219;
    }

    #suggestion-tree {
        background: #0b2630;
        color: #caf0f8;
        border-right: solid #00b4d8;
    }

    #suggestion-tree:focus {
        border-right: solid #90e0ef;
    }

    #suggestion-summary {
        color: #90e0ef;
        padding: 1 1;
    }

    #approval-pane {
        background: #071820;
        color: #f4fbfd;
        scrollbar-color: #00b4d8;
        scrollbar-color-hover: #48cae4;
        scrollbar-color-active: #90e0ef;
    }

    Button {
        background: #00b4d8;
        color: #001219;
        margin: 1;
    }

    Button.--danger {
        background: #e63946;
        color: #f4fbfd;
    }

    .score-green {
        color: #2ecc71;
        text-style: bold;
    }

    .score-blue {
        color: #3498db;
        text-style: bold;
    }

    .score-white {
        color: #f4fbfd;
    }

    .score-gray {
        color: #7f8c8d;
    }

    Footer {
        background: #0b2630;
        color: #caf0f8;
    }
    """
    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("space", "toggle_checkbox", "Toggle selection"),
        ("a", "select_all", "Select all visible"),
        ("n", "select_none", "Clear selection"),
    ]

    def __init__(
        self,
        structured_data: SuggestionStructuredData,
    ) -> None:
        super().__init__()
        self._data: SuggestionStructuredData = structured_data
        self._category_checked: Set[str] = set()
        self._file_checked: Set[Tuple[str, str]] = set()
        self._category_nodes: Dict[str, TreeNode[Any]] = {}
        self._file_nodes: Dict[Tuple[str, str], TreeNode[Any]] = {}

    @staticmethod
    def _score_class(score: float) -> str:
        if score >= 1.0 - 1e-9:
            return "score-green"
        if score >= 0.80:
            return "score-blue"
        if score >= 0.50:
            return "score-white"
        return "score-gray"

    @staticmethod
    def _format_score(score: float) -> str:
        return f"{score:.2f}"

    @staticmethod
    def _checkbox_mark(checked: bool) -> str:
        return "[x]" if checked else "[ ]"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        tree: Tree[Any] = Tree(
            "Contexto / Context",
            id="suggestion-tree",
        )
        tree.show_root = False
        yield Horizontal(
            tree,
            VerticalScroll(
                Label(
                    "Selecione os termos e arquivos para aprovar. Pressione ENTER para abrir/fechar e ESPAÇO para marcar.",
                    id="suggestion-summary",
                ),
                id="approval-pane",
            ),
        )
        yield Button("Cancel", id="cancel", variant="default", classes="--danger")
        yield Button("Aprove Selected", id="submit", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        tree: Tree[Any] = self.query_one("#suggestion-tree", Tree)
        root: TreeNode[Any] = tree.root
        root.expand()
        categories_count: int = len(self._data.categories)
        matched_section: TreeNode[Any] = root.add(
            f"📌 Categorias identificadas / Identified categories "
            f"({categories_count} termo{'s' if categories_count != 1 else ''})",
            data=("section", "matched"),
        )
        matched_section.expand()
        category: SuggestionCategoryEntry
        for category in self._data.categories:
            files_count: int = len(category.files)
            header: str = (
                f"🔖 {category.header} "
                f"({files_count} arquivo{'s' if files_count != 1 else ''})"
            )
            category_node: TreeNode[Any] = matched_section.add(
                header,
                data=("category", category.category_iri),
            )
            self._category_nodes[category.category_iri] = category_node
            self._refresh_category_node(category.category_iri)
            file_entry: SuggestionFileEntry
            for file_entry in category.files:
                score_label: str = (
                    f"  [{self._score_class(file_entry.best_score)}]"
                    f"(score {self._format_score(file_entry.best_score)})"
                    f"[/{self._score_class(file_entry.best_score)}]"
                )
                file_node: TreeNode[Any] = category_node.add_leaf(
                    f"📄 {file_entry.display_name}{score_label}",
                    data=(
                        "file",
                        category.category_iri,
                        file_entry.file_path,
                    ),
                )
                self._file_nodes[
                    (category.category_iri, file_entry.file_path)
                ] = file_node
                self._refresh_file_node(
                    category.category_iri, file_entry.file_path
                )
        if self._data.unmatched_files:
            unmatched_count: int = len(self._data.unmatched_files)
            unmatched_section: TreeNode[Any] = root.add(
                f"📌 Arquivos sem categoria definida / Unmatched files "
                f"({unmatched_count} arquivo{'s' if unmatched_count != 1 else ''})",
                data=("section", "unmatched"),
            )
            unmatched_section.expand()
            unmatched_bucket: TreeNode[Any] = unmatched_section.add(
                f"🔖 Unmatched chunks ({unmatched_count} arquivos)",
                data=("category", "__unmatched__"),
            )
            self._category_nodes["__unmatched__"] = unmatched_bucket
            self._refresh_category_node("__unmatched__")
            ufile: SuggestionFileEntry
            for ufile in self._data.unmatched_files:
                ufile_node: TreeNode[Any] = unmatched_bucket.add_leaf(
                    f"📄 {ufile.display_name}",
                    data=("file", "__unmatched__", ufile.file_path),
                )
                self._file_nodes[("__unmatched__", ufile.file_path)] = ufile_node
                self._refresh_file_node("__unmatched__", ufile.file_path)

    def _refresh_category_node(self, category_iri: str) -> None:
        node: Optional[TreeNode[Any]] = self._category_nodes.get(category_iri)
        if node is None:
            return
        original_label: str = node.label.plain
        mark: str = self._checkbox_mark(
            category_iri in self._category_checked
        )
        if original_label.strip().startswith("["):
            _prefix, _, rest = original_label.partition("]")
            new_label: str = f"{mark}{rest}"
        else:
            new_label = f"{mark} {original_label}"
        node.set_label(new_label)

    def _refresh_file_node(
        self,
        category_iri: str,
        file_path: str,
    ) -> None:
        node: Optional[TreeNode[Any]] = self._file_nodes.get(
            (category_iri, file_path)
        )
        if node is None:
            return
        original_text: str = node.label.plain
        mark: str = self._checkbox_mark(
            (category_iri, file_path) in self._file_checked
        )
        if original_text.strip().startswith("["):
            _prefix, _, rest = original_text.partition("]")
            new_text = f"{mark}{rest}"
        else:
            new_text = f"{mark} {original_text}"
        node.set_label(new_text)

    def _toggle_category(self, category_iri: str) -> None:
        if category_iri in self._category_checked:
            self._category_checked.discard(category_iri)
            files_to_uncheck: List[Tuple[str, str]] = [
                key
                for key in self._file_checked
                if key[0] == category_iri
            ]
            for key in files_to_uncheck:
                self._file_checked.discard(key)
        else:
            self._category_checked.add(category_iri)
            for category in self._data.categories:
                if category.category_iri == category_iri:
                    for fe in category.files:
                        self._file_checked.add((category_iri, fe.file_path))
                    break
            if category_iri == "__unmatched__":
                for ufe in self._data.unmatched_files:
                    self._file_checked.add(("__unmatched__", ufe.file_path))
        self._refresh_category_node(category_iri)
        refresh_keys: List[Tuple[str, str]] = [
            key
            for key in self._file_nodes.keys()
            if key[0] == category_iri
        ]
        for key in refresh_keys:
            self._refresh_file_node(key[0], key[1])

    def _toggle_file(self, category_iri: str, file_path: str) -> None:
        key: Tuple[str, str] = (category_iri, file_path)
        if key in self._file_checked:
            self._file_checked.discard(key)
            self._category_checked.discard(category_iri)
        else:
            self._file_checked.add(key)
            all_files_for_cat: Set[str] = set()
            for category in self._data.categories:
                if category.category_iri == category_iri:
                    for fe in category.files:
                        all_files_for_cat.add(fe.file_path)
                    break
            if category_iri == "__unmatched__":
                for ufe in self._data.unmatched_files:
                    all_files_for_cat.add(ufe.file_path)
            checked_files: Set[str] = {
                k[1]
                for k in self._file_checked
                if k[0] == category_iri
            }
            if checked_files == all_files_for_cat:
                self._category_checked.add(category_iri)
        self._refresh_file_node(category_iri, file_path)
        self._refresh_category_node(category_iri)

    async def action_toggle_checkbox(self) -> None:
        tree: Tree[Any] = self.query_one("#suggestion-tree", Tree)
        node: TreeNode[Any] = tree.cursor_node
        self._handle_toggle(node)

    def _handle_toggle(self, node: TreeNode[Any]) -> None:
        data: Any = node.data
        if not isinstance(data, tuple) or not data:
            return
        kind: Any = data[0]
        if kind == "category":
            self._toggle_category(str(data[1]))
        elif kind == "file" and len(data) >= 3:
            self._toggle_file(str(data[1]), str(data[2]))

    async def action_select_all(self) -> None:
        for category in self._data.categories:
            self._category_checked.add(category.category_iri)
            for fe in category.files:
                self._file_checked.add((category.category_iri, fe.file_path))
        if self._data.unmatched_files:
            self._category_checked.add("__unmatched__")
            for ufe in self._data.unmatched_files:
                self._file_checked.add(("__unmatched__", ufe.file_path))
        for cat_iri in list(self._category_nodes.keys()):
            self._refresh_category_node(cat_iri)
        for file_key in list(self._file_nodes.keys()):
            self._refresh_file_node(file_key[0], file_key[1])

    async def action_select_none(self) -> None:
        self._category_checked.clear()
        self._file_checked.clear()
        for cat_iri in list(self._category_nodes.keys()):
            self._refresh_category_node(cat_iri)
        for file_key in list(self._file_nodes.keys()):
            self._refresh_file_node(file_key[0], file_key[1])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.exit(None)
        elif event.button.id == "submit":
            selected_cats: List[str] = sorted(self._category_checked)
            files_by_cat: Dict[str, List[str]] = {}
            for (cat_iri, fpath) in self._file_checked:
                if cat_iri not in files_by_cat:
                    files_by_cat[cat_iri] = []
                files_by_cat[cat_iri].append(fpath)
            result_list: List[Tuple[str, Tuple[str, ...]]] = []
            for cat_iri in selected_cats:
                flist: List[str] = sorted(files_by_cat.get(cat_iri, []))
                result_list.append((cat_iri, tuple(flist)))
            self.exit(
                SuggestionApprovalResult(
                    selected_categories=tuple(selected_cats),
                    selected_files_by_category=tuple(result_list),
                )
            )


class SuggestionApprovalAdapter:
    def open(
        self,
        structured_data: SuggestionStructuredData,
    ) -> Optional[SuggestionApprovalResult]:
        app: SuggestionApprovalApp = SuggestionApprovalApp(structured_data)
        result: Optional[SuggestionApprovalResult] = app.run()
        return result
