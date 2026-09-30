from typing import Any, ClassVar, Dict, List, Optional, Tuple
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree
from textual.widgets.tree import TreeNode

from ontobdc.cli.domain.port.widget import Widget
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.storage.plugin.machine.open_file.port import FileOpenResult, OpenFileChainSupport
from ontobdc.storage.plugin.machine.open_file.machine import OpenFileMachine


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

_FILE_OPEN_KINDS: Tuple[str, ...] = ("file", "drawing", "model")


_DEFAULT_LANGUAGE: str = "en"
# Translation dictionary (keys = normalized language codes, values = message dict).
# Keys follow the i18n convention adopted by the project (see state.py helpers):
# lower-case, dash-separated (pt-br not pt_BR; es; pt-pt).
_MESSAGE_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "open_file_title": "Open file",
        "error_cannot_open": "Unable to open the file.",
        "success_opened": "File opened.",
        "warn_select_file_only": (
            "Shortcut 'o' opens files only (individual models, drawings, "
            "and file entries). Expand a category folder and pick a leaf "
            "file to open it."
        ),
        "warn_select_leaf_folder": (
            "Shortcut 'o' opens files only. «{name}» is a folder "
            "(directory). Expand it and pick a file inside it."
        ),
        "error_no_kind_metadata": (
            "Selected node has no kind metadata; cannot decide whether it "
            "is openable."
        ),
        "warn_kind_not_file": (
            "Shortcut 'o' applies to file-like nodes "
            "('file'/'model'/'drawing'). This one is kind={kind!r}. "
            "Pick a file entry."
        ),
        "error_no_metadata": "Selected file node has no metadata payload.",
    },
    "pt-br": {
        "open_file_title": "Abrir arquivo",
        "error_cannot_open": "Não foi possível abrir o arquivo.",
        "success_opened": "Arquivo aberto.",
        "warn_select_file_only": (
            "O atalho 'o' abre apenas arquivos (models, drawings e "
            "entradas de arquivo individuais). Expanda uma categoria e "
            "selecione um arquivo folha para abrir."
        ),
        "warn_select_leaf_folder": (
            "O atalho 'o' abre apenas arquivos. «{name}» é uma pasta "
            "(diretório). Expanda-a e selecione um arquivo dentro."
        ),
        "error_no_kind_metadata": (
            "O nó selecionado não tem metadado de kind; não é possível "
            "decidir se ele é abrível."
        ),
        "warn_kind_not_file": (
            "O atalho 'o' aplica-se a nós do tipo arquivo "
            "('file'/'model'/'drawing'). Este é kind={kind!r}. "
            "Selecione uma entrada de arquivo."
        ),
        "error_no_metadata": "O nó selecionado não tem payload de metadados.",
    },
    "pt-pt": {
        "open_file_title": "Abrir ficheiro",
        "error_cannot_open": "Não foi possível abrir o ficheiro.",
        "success_opened": "Ficheiro aberto.",
        "warn_select_file_only": (
            "O atalho 'o' abre apenas ficheiros (models, drawings e "
            "entradas de ficheiro individuais). Expanda uma categoria e "
            "selecione um ficheiro folha para abrir."
        ),
        "warn_select_leaf_folder": (
            "O atalho 'o' abre apenas ficheiros. «{name}» é uma pasta "
            "(diretório). Expanda-a e selecione um ficheiro dentro."
        ),
        "error_no_kind_metadata": (
            "O nó selecionado não tem metadado de kind; não é possível "
            "decidir se ele é abrível."
        ),
        "warn_kind_not_file": (
            "O atalho 'o' aplica-se a nós do tipo ficheiro "
            "('file'/'model'/'drawing'). Este é kind={kind!r}. "
            "Selecione uma entrada de ficheiro."
        ),
        "error_no_metadata": "O nó selecionado não tem payload de metadados.",
    },
    "es": {
        "open_file_title": "Abrir archivo",
        "error_cannot_open": "No se pudo abrir el archivo.",
        "success_opened": "Archivo abierto.",
        "warn_select_file_only": (
            "El atajo 'o' solo abre archivos (models, drawings y "
            "entradas de archivo individuales). Expanda una categoría y "
            "seleccione un archivo hoja para abrirlo."
        ),
        "warn_select_leaf_folder": (
            "El atajo 'o' solo abre archivos. «{name}» es una carpeta "
            "(directorio). Expándala y seleccione un archivo dentro."
        ),
        "error_no_kind_metadata": (
            "El nodo seleccionado no tiene metadato de kind; no es "
            "posible decidir si se puede abrir."
        ),
        "warn_kind_not_file": (
            "El atajo 'o' aplica a nodos tipo archivo "
            "('file'/'model'/'drawing'). Este es kind={kind!r}. "
            "Seleccione una entrada de archivo."
        ),
        "error_no_metadata": "El nodo seleccionado no tiene payload de metadatos.",
    },
}


def _normalize_language(lang: str) -> str:
    """
    Normalize a language tag to the convention used elsewhere in OntoBDC.

    Mirrors :meth:`_normalize_presentation_metadata` in
    :mod:`ontobdc.container.plugin.machine.container_create.state`: strips
    whitespace, lower-cases and replaces underscores with dashes so both
    ``pt_BR`` and ``pt-br`` resolve to the same entry.
    """
    return str(lang).strip().lower().replace("_", "-")


def _translate(lang: str, key: str, **kwargs: Any) -> str:
    """
    Return a translated string, falling back through English.

    Resolution order: (1) normalized ``lang`` entry, (2) ``"en"`` entry,
    (3) raw ``key`` so the surface still shows *something* if a key is
    mistyped rather than silently showing an empty bubble.
    """
    normalized: str = _normalize_language(lang)
    table: Dict[str, str] = _MESSAGE_TRANSLATIONS.get(
        normalized, _MESSAGE_TRANSLATIONS[_DEFAULT_LANGUAGE]
    )
    if key in table:
        return table[key].format(**kwargs)

    fallback_en: Dict[str, str] = _MESSAGE_TRANSLATIONS.get(
        _DEFAULT_LANGUAGE, {}
    )
    if key in fallback_en:
        return fallback_en[key].format(**kwargs)

    return key


class InteractiveTreeApp(App[None]):
    """Textual TUI for an OntoBDC/InfoBIM tree dictionary."""

    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("f", "focus_tree", "Focus tree"),
        ("e", "expand_all", "Expand all"),
        ("c", "collapse_all", "Collapse all"),
        ("o", "open_file", "Open file"),
    ]

    TITLE_BINDINGS: ClassVar[List[Tuple[str, str]]] = [
        ("Enter/Space", "Toggle collapse/expand"),
        ("←/→", "Collapse/expand node"),
        ("↑/↓", "Move selection"),
        ("/", "Search (Textual native)"),
        ("e", "Expand all"),
        ("c", "Collapse all"),
        ("f", "Focus tree"),
        ("o", "Open selected file (drawing/model/file)"),
        ("q", "Quit"),
    ]

    CSS = """
    Tree {
        width: 100%;
        height: 100%;
    }
    Header {
        dock: top;
    }
    Footer {
        dock: bottom;
    }
    """

    def __init__(
        self,
        title: str,
        description: str,
        tree_root: Dict[str, Any],
        context: CliContextPort,
        content_root_path: Optional[Path] = None,
        language: Optional[str] = None,
        plugin_root_packages: Tuple[str, ...] = ("ontobdc",),
    ) -> None:
        super().__init__()
        self._cli_context: CliContextPort = context
        self._tree_title: str = title
        self._tree_description: str = description
        self._tree_root: Dict[str, Any] = tree_root
        self._content_root_path: Optional[Path] = (
            content_root_path.expanduser().resolve()
            if content_root_path is not None
            else None
        )
        self._language: str = (
            _normalize_language(language) if language is not None else _DEFAULT_LANGUAGE
        )
        self._plugin_root_packages: Tuple[str, ...] = plugin_root_packages

    def _t(self, key: str, **kwargs: Any) -> str:
        return _translate(self._language, key, **kwargs)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Tree[Any](self._root_label(), id="ontobdc-tree")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self._tree_title
        self.sub_title = self._tree_description
        tree: Tree[Any] = self.query_one(Tree[Any])
        tree.show_root = True
        tree.root.data = self._tree_root
        self._populate(tree.root, self._tree_root)
        tree.root.expand()

    def action_focus_tree(self) -> None:
        tree: Tree[Any] = self.query_one(Tree[Any])
        tree.focus()

    def action_expand_all(self) -> None:
        tree: Tree[Any] = self.query_one(Tree[Any])
        tree.root.expand_all()

    def action_collapse_all(self) -> None:
        tree: Tree[Any] = self.query_one(Tree[Any])
        tree.root.collapse_all()

    def action_open_file(self) -> None:
        """Open the file associated with the currently selected tree node."""
        tree: Tree[Any] = self.query_one(Tree[Any])
        selected: Optional[TreeNode[Any]] = tree.cursor_node
        if selected is None or selected is tree.root:
            self.notify(
                self._t("warn_select_file_only"),
                title=self._t("open_file_title"),
                severity="warning",
            )
            return

        node_data: Any = selected.data
        has_data: bool = isinstance(node_data, dict)

        openable_override: Optional[bool] = (
            bool(node_data["openable"])
            if has_data and "openable" in node_data
            else None
        )
        kind: Optional[str] = None
        if has_data and "kind" in node_data:
            raw_kind: Any = node_data["kind"]
            if not isinstance(raw_kind, str):
                raise TypeError(
                    f"TreeNode dict metadata field 'kind' must be str; "
                    f"got {type(raw_kind).__name__} ({raw_kind!r})"
                )
            kind = raw_kind
        if kind is None:
            self.notify(
                self._t("error_no_kind_metadata"),
                title=self._t("open_file_title"),
                severity="error",
            )
            return

        is_openable: bool = (
            openable_override
            if openable_override is not None
            else kind in _FILE_OPEN_KINDS
        )
        if not is_openable:
            self.notify(
                self._t("warn_select_file_only"),
                title=self._t("open_file_title"),
                severity="warning",
            )
            return
        if kind not in _FILE_OPEN_KINDS and openable_override is None:
            self.notify(
                self._t("warn_kind_not_file", kind=kind),
                title=self._t("open_file_title"),
                severity="warning",
            )
            return

        if not has_data:
            self.notify(
                self._t("error_no_metadata"),
                title=self._t("open_file_title"),
                severity="error",
            )
            return

        raw_name: Any = node_data["name"]
        if not isinstance(raw_name, str):
            raise TypeError(
                f"TreeNode dict metadata field 'name' must be str; "
                f"got {type(raw_name).__name__} ({raw_name!r})"
            )
        name: str = raw_name
        path: Optional[Path] = self._resolve_node_path(selected, node_data)
        if path is not None and path.exists() and path.is_dir():
            self.notify(
                self._t("warn_select_leaf_folder", name=name),
                title=self._t("open_file_title"),
                severity="warning",
            )
            return

        self._cli_context.set_parameter_value(OpenFileChainSupport.KIND_KEY, kind)
        self._cli_context.set_parameter_value(OpenFileChainSupport.NAME_KEY, name)
        self._cli_context.set_parameter_value(
            OpenFileChainSupport.DATA_KEY,
            dict(node_data),
        )
        self._cli_context.set_parameter_value(
            OpenFileChainSupport.LANGUAGE_KEY,
            self._language,
        )
        if path is None:
            self._cli_context.delete_parameter(OpenFileChainSupport.PATH_KEY)
        else:
            self._cli_context.set_parameter_value(
                OpenFileChainSupport.PATH_KEY,
                str(path),
            )

        machine: OpenFileMachine = OpenFileMachine(
            context=self._cli_context,
            root_packages=self._plugin_root_packages,
        )
        result: FileOpenResult = self._file_open_result(machine.work())
        handler_label: str = f" ({result.handler})" if result.handler else ""

        if result.handled and result.error:
            self.notify(
                self._t("error_cannot_open"),
                title=self._t("open_file_title"),
                severity="error",
            )
            self.log.error(
                "Open file failed%s: kind=%r name=%r resolved_path=%s error=%s",
                handler_label,
                kind,
                name,
                str(path) if path is not None else "<unresolved>",
                result.error,
            )
            return

        if result.handled:
            body: str = (
                result.message if result.message else self._t("success_opened")
            )
            self.notify(body, title=self._t("open_file_title"), severity="information")
            self.log.info(
                "Open file succeeded%s: kind=%r name=%r resolved_path=%s message=%r",
                handler_label,
                kind,
                name,
                str(path) if path is not None else "<unresolved>",
                result.message,
            )
            return

        self.notify(
            self._t("error_cannot_open"),
            title=self._t("open_file_title"),
            severity="error",
        )
        self.log.warning(
            "Open file unhandled%s — kind=%r name=%r resolved_path=%s",
            handler_label,
            kind,
            name,
            str(path) if path is not None else "<unresolved>",
        )

    @staticmethod
    def _file_open_result(
        results: Dict[str, Dict[str, Any]],
    ) -> FileOpenResult:
        capability_id: str
        payload: Dict[str, Any]
        for capability_id, payload in results.items():
            if payload.get("handled") is not True:
                continue

            handler: Any = payload.get("handler")
            message: Any = payload.get("message")
            error: Any = payload.get("error")
            return FileOpenResult(
                handled=True,
                handler=(
                    handler
                    if isinstance(handler, str) and handler
                    else capability_id.rsplit(".", 1)[-1]
                ),
                message=message if isinstance(message, str) else "",
                error=error if isinstance(error, str) else None,
            )

        return FileOpenResult(
            handled=False,
            error="No open-file capability handled the file.",
        )

    def _resolve_node_path(
        self,
        node: TreeNode[Any],
        node_data: Dict[str, Any],
    ) -> Optional[Path]:
        explicit: Any = node_data["path"] if "path" in node_data else None
        if isinstance(explicit, (str, Path)) and str(explicit).strip():
            candidate: Path = Path(str(explicit)).expanduser()
            if candidate.is_absolute():
                return candidate
            if self._content_root_path is not None:
                return (self._content_root_path / candidate).resolve()
            return candidate

        if self._content_root_path is None:
            return None

        segments: List[str] = []
        cursor: Optional[TreeNode[Any]] = node
        while cursor is not None:
            data: Any = cursor.data
            if isinstance(data, dict) and "name" in data:
                raw_segment: Any = data["name"]
                if not isinstance(raw_segment, str):
                    raise TypeError(
                        f"TreeNode dict metadata field 'name' must be str; "
                        f"got {type(raw_segment).__name__} ({raw_segment!r})"
                    )
                segment_name: str = raw_segment.strip()
            else:
                segment_name = ""
            if segment_name:
                segments.append(segment_name)
            cursor = cursor.parent

        segments_reversed: List[str] = list(reversed(segments))
        if segments_reversed:
            segments_reversed = segments_reversed[1:]
        if not segments_reversed:
            return None

        return (self._content_root_path.joinpath(*segments_reversed)).resolve()

    @classmethod
    def _populate(cls, textual_node: TreeNode[Any], dict_node: Dict[str, Any]) -> None:
        if "children" not in dict_node:
            children: List[Dict[str, Any]] = []
        else:
            raw_children: Any = dict_node["children"]
            if not isinstance(raw_children, list):
                raise TypeError(
                    f"TreeNode dict metadata field 'children' must be list; "
                    f"got {type(raw_children).__name__} ({raw_children!r})"
                )
            children = [c for c in raw_children if isinstance(c, dict)]
        for child in children:
            label: str = cls._node_label(child)
            if "children" not in child:
                grandkids: List[Dict[str, Any]] = []
            else:
                raw_grandkids: Any = child["children"]
                if not isinstance(raw_grandkids, list):
                    raise TypeError(
                        f"TreeNode dict child metadata field 'children' must "
                        f"be list; got {type(raw_grandkids).__name__} "
                        f"({raw_grandkids!r})"
                    )
                grandkids = [g for g in raw_grandkids if isinstance(g, dict)]
            added: TreeNode[Any] = textual_node.add(
                label,
                data=child,
                allow_expand=bool(grandkids),
            )
            if grandkids:
                cls._populate(added, child)

    def _root_label(self) -> str:
        return self._node_label(self._tree_root)

    @classmethod
    def _node_label(cls, node: Dict[str, Any]) -> str:
        raw_kind: Any = node["kind"]
        if not isinstance(raw_kind, str):
            raise TypeError(
                f"TreeNode dict metadata field 'kind' must be str; "
                f"got {type(raw_kind).__name__} ({raw_kind!r})"
            )
        kind: str = raw_kind
        if kind not in _ICONS:
            raise KeyError(
                f"TreeNode dict metadata field 'kind'={kind!r} is not a "
                f"registered icon kind. Registered kinds: "
                f"{sorted(_ICONS.keys())!r}"
            )
        icon: str = _ICONS[kind]
        raw_name: Any = node["name"]
        if not isinstance(raw_name, str):
            raise TypeError(
                f"TreeNode dict metadata field 'name' must be str; "
                f"got {type(raw_name).__name__} ({raw_name!r})"
            )
        name: str = raw_name
        return f"{icon}  {name}" if icon else name


class InteractiveTreeWidget(Widget):
    """Entry-point widget used by commands."""

    root: Dict[str, Any] = {}
    title: str = "Tree Viewer"
    description: str = "Interactive collapsible tree view."
    content_root_path: Optional[Path] = None
    language: Optional[str] = None
    plugin_root_packages: Tuple[str, ...] = ("ontobdc",)
    context: Optional[CliContextPort] = None

    def render(self, available_columns: int) -> List[str]:
        return []

    def show(self) -> None:
        if self.context is None:
            raise ValueError(
                "InteractiveTreeWidget requires the command context before show()."
            )

        app = InteractiveTreeApp(
            title=self.title,
            description=self.description,
            tree_root=self.root,
            context=self.context,
            content_root_path=self.content_root_path,
            language=self.language,
            plugin_root_packages=self.plugin_root_packages,
        )
        app.run(headless=False)
