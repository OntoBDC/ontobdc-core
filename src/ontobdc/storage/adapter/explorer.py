import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Set, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Markdown, MarkdownViewer, Tree
from textual.widgets.tree import TreeNode

from ontobdc.context.adapter.dataset_instance import (
    DatasetEntityInstanceRepository,
)
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.port.component import (
    ComponentPort,
    TerminalTileRenderable,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


@dataclass(frozen=True)
class StorageElementFacadeContent:
    entity_name: str
    facade_name: str
    field_names: Tuple[str, ...]
    records: List[Dict[str, Any]]


class StorageElementContentAdapter:
    """Project source records strictly through their declared facade."""

    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"
    FACADE_FILE_NAME: ClassVar[str] = "facade.ttl"

    def load(
        self,
        element: Dict[str, Any],
    ) -> Optional[StorageElementFacadeContent]:
        dataset_path: str = str(element.get("dataset_path") or "").strip()
        entity_reference: str = str(
            element.get("entity_uri")
            or element.get("entity_identifier")
            or ""
        ).strip()
        facade_uri: str = str(element.get("facade_uri") or "").strip()
        if not dataset_path or not entity_reference or not facade_uri:
            return None

        facade_path: Path = (
            StorageBootstrap.get_ontobdc_directory(Path(dataset_path))
            / self.LINKSET_DIRECTORY_NAME
            / self.FACADE_FILE_NAME
        )
        facade_subject: URIRef = URIRef(facade_uri)
        facade_graph: Optional[Graph] = self._facade_graph(
            facade_path=facade_path,
            facade_subject=facade_subject,
        )
        if facade_graph is None:
            return None
        field_names: Tuple[str, ...] = self._facade_field_names(
            facade_graph,
            facade_subject,
        )
        if not field_names:
            return None

        payload: Dict[str, Any] = DatasetEntityInstanceRepository(
            dataset_path=dataset_path,
            entity=entity_reference,
        ).list_instances()
        source_records: List[Dict[str, Any]] = list(
            payload.get("instances") or []
        )
        projected_records: List[Dict[str, Any]] = [
            {
                field_name: source_record.get(field_name)
                for field_name in field_names
            }
            for source_record in source_records
        ]
        return StorageElementFacadeContent(
            entity_name=self._local_name(
                element.get("entity_uri") or entity_reference
            ),
            facade_name=self._facade_name(facade_graph, facade_subject),
            field_names=field_names,
            records=projected_records,
        )

    def _facade_graph(
        self,
        *,
        facade_path: Path,
        facade_subject: URIRef,
    ) -> Optional[Graph]:
        if not facade_path.is_file():
            return None
        graph: Graph = Graph()
        graph.parse(str(facade_path), format="turtle")
        if not self._facade_field_names(graph, facade_subject):
            return None
        return graph

    def _facade_field_names(
        self,
        graph: Graph,
        facade_subject: URIRef,
    ) -> Tuple[str, ...]:
        field_orders: Dict[str, Optional[int]] = {}
        predicate: Any
        field_subject: Any
        for predicate, field_subject in graph.predicate_objects(facade_subject):
            if self._local_name(predicate) != "hasFacadeField":
                continue
            field_name: str = ""
            field_order: Optional[int] = None
            field_predicate: Any
            field_value: Any
            for field_predicate, field_value in graph.predicate_objects(
                field_subject
            ):
                predicate_name: str = self._local_name(field_predicate)
                if predicate_name == "identifier" and isinstance(
                    field_value,
                    Literal,
                ):
                    field_name = str(field_value).strip()
                elif predicate_name == "fieldOrder" and isinstance(
                    field_value,
                    Literal,
                ):
                    field_order = int(str(field_value))
            if field_name:
                field_orders[field_name] = field_order
        ordered_fields: List[Tuple[str, Optional[int]]] = sorted(
            field_orders.items(),
            key=lambda field: (
                field[1] is None,
                field[1] if field[1] is not None else 0,
                field[0],
            ),
        )
        return tuple(field_name for field_name, _ in ordered_fields)

    def _facade_name(self, graph: Graph, facade_subject: URIRef) -> str:
        predicate: Any
        value: Any
        for predicate, value in graph.predicate_objects(facade_subject):
            if (
                self._local_name(predicate) == "name"
                and isinstance(value, Literal)
            ):
                name: str = str(value).strip()
                if name:
                    return name
        return self._local_name(facade_subject)

    def resolve_standalone_tile_classes(
        self,
        *,
        facade_path: Path,
        facade_subject: URIRef,
    ) -> List[str]:
        """Ordered ``tile_class`` URIs the facade declares via
        ``hasStandaloneTile`` / ``placesComponent`` / ``placementOrder``
        (matched by local name, so this works with any facade vocabulary
        that reuses the OntoBDC View Ontology's placement shape).

        Empty when the facade declares no standalone tiles at all — the
        caller (:meth:`StorageElementMarkdownAdapter.build_standalone`)
        falls back to the default field/value document in that case.
        """
        if not facade_path.is_file():
            return []
        graph: Graph = Graph()
        graph.parse(str(facade_path), format="turtle")

        placements: List[Tuple[int, str]] = []
        predicate: Any
        placement_subject: Any
        for predicate, placement_subject in graph.predicate_objects(
            facade_subject
        ):
            if self._local_name(predicate) != "hasStandaloneTile":
                continue

            tile_individual: Optional[Any] = None
            placement_order: int = 0
            field_predicate: Any
            field_value: Any
            for field_predicate, field_value in graph.predicate_objects(
                placement_subject
            ):
                predicate_name: str = self._local_name(field_predicate)
                if predicate_name == "placesComponent":
                    tile_individual = field_value
                elif (
                    predicate_name == "placementOrder"
                    and isinstance(field_value, Literal)
                ):
                    try:
                        placement_order = int(str(field_value))
                    except ValueError:
                        placement_order = 0

            if tile_individual is None:
                continue

            tile_class_uri: str = ""
            for type_object in graph.objects(tile_individual, RDF.type):
                candidate: str = str(type_object)
                if self._local_name(candidate) == "NamedIndividual":
                    continue
                tile_class_uri = candidate
                break

            if tile_class_uri:
                placements.append((placement_order, tile_class_uri))

        placements.sort(key=lambda placement: placement[0])
        return [tile_class_uri for _, tile_class_uri in placements]

    @staticmethod
    def _local_name(value: Any) -> str:
        raw_value: str = str(value or "").strip()
        if "#" in raw_value:
            return raw_value.rsplit("#", 1)[-1]
        return raw_value.rstrip("/").rsplit("/", 1)[-1]


class StorageElementMarkdownAdapter:
    """Build the Markdown document displayed by the element explorer."""

    DIMENSION_NAMES: ClassVar[Tuple[str, ...]] = (
        "What",
        "Why",
        "Who",
        "Where",
        "When",
        "How",
        "HowMuch",
    )

    def __init__(
        self,
        content_adapter: StorageElementContentAdapter | None = None,
    ) -> None:
        self._content_adapter: StorageElementContentAdapter = (
            content_adapter or StorageElementContentAdapter()
        )

    def build(
        self,
        *,
        elements: List[Dict[str, Any]],
    ) -> str:
        lines: List[str] = ["# Entity Element Explorer", ""]

        facade_index: int = 0
        for element in elements:
            facade_content: Optional[StorageElementFacadeContent] = (
                self._content_adapter.load(element)
            )
            if facade_content is None:
                continue
            facade_index += 1
            element_title: str = str(element.get("title") or "").strip()
            lines.extend(
                [
                    f"## {facade_index}. {element_title}",
                    "",
                ]
            )
            for record_index, content in enumerate(
                facade_content.records,
                start=1,
            ):
                heading_prefix: str = "###"
                if len(facade_content.records) > 1:
                    lines.extend([f"### Record {record_index}", ""])
                    heading_prefix = "####"
                dimensions: List[Tuple[str, Any]] = [
                    (name, content[name])
                    for name in self.DIMENSION_NAMES
                    if name in content
                ]
                dimension_names: Set[str] = {
                    dimension_name for dimension_name, _ in dimensions
                }
                fields: List[Tuple[str, Any]] = [
                    (str(name), value)
                    for name, value in content.items()
                    if str(name) not in dimension_names
                ]
                self._append_value_table(
                    lines,
                    facade_content.entity_name,
                    fields,
                    heading_prefix=heading_prefix,
                )
                self._append_value_table(
                    lines,
                    "Dimensions",
                    dimensions,
                    heading_prefix=heading_prefix,
                )

        return "\n".join(lines)

    def build_one(self, element: Dict[str, Any]) -> Optional[str]:
        """Build the Markdown for a single element only.

        Used by the lazy explorer (:class:`StorageElementLazyExplorerApp`),
        which computes and renders one element's facade content only when
        its tree node is selected, instead of every element upfront the
        way :meth:`build` does. ``build`` itself is untouched and still
        produces the single continuous document — a good fit for
        printable reports — that :class:`StorageElementExplorerApp` shows.
        """
        facade_content: Optional[StorageElementFacadeContent] = (
            self._content_adapter.load(element)
        )
        if facade_content is None:
            return None

        element_title: str = str(element.get("title") or "").strip()
        lines: List[str] = [
            f"# {element_title}" if element_title else "# Element",
            "",
        ]
        for record_index, content in enumerate(facade_content.records, start=1):
            heading_prefix: str = "##"
            if len(facade_content.records) > 1:
                lines.extend([f"## Record {record_index}", ""])
                heading_prefix = "###"
            dimensions: List[Tuple[str, Any]] = [
                (name, content[name])
                for name in self.DIMENSION_NAMES
                if name in content
            ]
            dimension_names: Set[str] = {
                dimension_name for dimension_name, _ in dimensions
            }
            fields: List[Tuple[str, Any]] = [
                (str(name), value)
                for name, value in content.items()
                if str(name) not in dimension_names
            ]
            self._append_value_table(
                lines,
                facade_content.entity_name,
                fields,
                heading_prefix=heading_prefix,
            )
            self._append_value_table(
                lines,
                "Dimensions",
                dimensions,
                heading_prefix=heading_prefix,
            )

        return "\n".join(lines)

    def build_standalone_tiles(
        self,
        element: Dict[str, Any],
        *,
        width: int = 100,
    ) -> List[str]:
        """Render this element's facade-declared standalone Tiles.

        Resolves ``hasStandaloneTile`` placements (see
        :meth:`StorageElementContentAdapter.resolve_standalone_tile_classes`)
        through the same :class:`ComponentLoader` the terminal and HTML
        Surfaces already use, keeps only implementations that are also
        :class:`TerminalTileRenderable`, and renders each with the matched
        element passed in as ``context["element"]``. Returns an empty list
        when the facade declares no standalone tiles, or none of the
        declared tile classes resolve to a terminal-renderable
        implementation — the caller (:meth:`build_standalone`) falls back
        to the plain field/value document in that case.
        """
        dataset_path: str = str(element.get("dataset_path") or "").strip()
        facade_uri: str = str(element.get("facade_uri") or "").strip()
        if not dataset_path or not facade_uri:
            return []

        facade_path: Path = (
            StorageBootstrap.get_ontobdc_directory(Path(dataset_path))
            / StorageElementContentAdapter.LINKSET_DIRECTORY_NAME
            / StorageElementContentAdapter.FACADE_FILE_NAME
        )
        tile_class_uris: List[str] = (
            self._content_adapter.resolve_standalone_tile_classes(
                facade_path=facade_path,
                facade_subject=URIRef(facade_uri),
            )
        )
        if not tile_class_uris:
            return []

        loader: ComponentLoader = ComponentLoader()
        rendered_tiles: List[str] = []
        for tile_class_uri in tile_class_uris:
            matches: List[type[ComponentPort]] = [
                component_type
                for component_type in loader.match_tile_class(tile_class_uri)
                if issubclass(component_type, TerminalTileRenderable)
            ]
            if not matches:
                continue
            tile: TerminalTileRenderable = matches[0]()  # type: ignore[call-arg]
            rendered_tiles.append(
                tile.render(columns=width, rows=1, context={"element": element})
            )
        return rendered_tiles

    def build_standalone(
        self,
        element: Dict[str, Any],
        *,
        width: int = 100,
    ) -> str:
        """Full standalone-view document for one element.

        Facade-declared Tiles when any resolve (see
        :meth:`build_standalone_tiles`), otherwise the same
        facade-projected field/value document :meth:`build_one` already
        produces, otherwise a plain "no content" notice.
        """
        element_title: str = str(element.get("title") or "").strip()
        heading: str = f"# {element_title}" if element_title else "# Element"

        tile_lines: List[str] = self.build_standalone_tiles(element, width=width)
        if tile_lines:
            return "\n\n".join([heading, *tile_lines])

        field_value_document: Optional[str] = self.build_one(element)
        if field_value_document:
            return field_value_document

        return (
            f"{heading}\n\n"
            f"_No facade content available for "
            f"**{element_title or 'this element'}**._"
        )

    def _append_value_table(
        self,
        lines: List[str],
        heading: str,
        values: Iterable[Tuple[str, Any]],
        *,
        heading_prefix: str,
    ) -> None:
        rows: List[Tuple[str, Any]] = list(values)
        if not rows:
            return
        lines.extend(
            [
                f"{heading_prefix} {heading}",
                "",
                "| Field | Value |",
                "| --- | --- |",
                *[
                    f"| {self._cell(name)} | {self._cell(value)} |"
                    for name, value in rows
                ],
                "",
            ]
        )

    @staticmethod
    def _cell(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, (dict, list, tuple)):
            rendered_value: str = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
        else:
            rendered_value = str(value)
        return rendered_value.replace("|", "\\|").replace("\n", "<br>")


class StorageElementExplorerApp(App[None]):
    """Standalone Textual application for storage element Markdown."""

    TITLE: ClassVar[str] = "OntoBDC"
    SUB_TITLE: ClassVar[str] = "Storage Element Explorer"
    CSS: ClassVar[str] = """
    Screen {
        background: #071820;
        color: #f4fbfd;
    }

    Header {
        background: #00b4d8;
        color: #001219;
    }

    MarkdownViewer {
        background: #071820;
        color: #f4fbfd;
        scrollbar-color: #00b4d8;
        scrollbar-color-hover: #48cae4;
        scrollbar-color-active: #90e0ef;
    }

    MarkdownTableOfContents {
        background: #0b2630;
        color: #caf0f8;
        border-right: solid #00b4d8;
        width: 36;
    }

    Footer {
        background: #0b2630;
        color: #caf0f8;
    }
    """
    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    def __init__(self, markdown: str) -> None:
        super().__init__()
        self._markdown: str = markdown

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield MarkdownViewer(
            self._markdown,
            show_table_of_contents=True,
            open_links=True,
            id="element-markdown-viewer",
        )
        yield Footer()


class StorageElementLazyExplorerApp(App[None]):
    """Standalone Textual application with a real element Tree.

    Unlike :class:`StorageElementExplorerApp` (kept as-is: one big
    pre-rendered Markdown document with an auto-generated table of
    contents — good for a continuous read or a printable report), this
    app only computes and renders one element's facade content — via
    :meth:`StorageElementMarkdownAdapter.build_one` — when its node is
    actually selected in the sidebar tree. Nothing is loaded up front
    beyond the (cheap, already-in-memory) element titles, and each
    element's rendered Markdown is cached after its first load so
    re-selecting the same node doesn't redo the work.
    """

    TITLE: ClassVar[str] = "OntoBDC"
    SUB_TITLE: ClassVar[str] = "Storage Element Explorer"
    CSS: ClassVar[str] = """
    Screen {
        background: #071820;
        color: #f4fbfd;
    }

    Header {
        background: #00b4d8;
        color: #001219;
    }

    #element-tree {
        background: #0b2630;
        color: #caf0f8;
        border-right: solid #00b4d8;
        width: 36;
    }

    #element-content-pane {
        background: #071820;
        color: #f4fbfd;
        scrollbar-color: #00b4d8;
        scrollbar-color-hover: #48cae4;
        scrollbar-color-active: #90e0ef;
    }

    Footer {
        background: #0b2630;
        color: #caf0f8;
    }
    """
    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ]

    def __init__(
        self,
        elements: List[Dict[str, Any]],
        markdown_adapter: StorageElementMarkdownAdapter | None = None,
    ) -> None:
        super().__init__()
        self._elements: List[Dict[str, Any]] = elements
        self._markdown_adapter: StorageElementMarkdownAdapter = (
            markdown_adapter or StorageElementMarkdownAdapter()
        )
        self._rendered_cache: Dict[int, str] = {}

    def compose(self) -> ComposeResult:
        tree: Tree[int] = Tree("Elements", id="element-tree")
        tree.show_root = False
        markdown_pane: Markdown = Markdown(
            "Select an element on the left.",
            id="element-markdown",
        )
        yield Header(show_clock=False)
        yield Horizontal(
            tree,
            VerticalScroll(markdown_pane, id="element-content-pane"),
        )
        yield Footer()

    def on_mount(self) -> None:
        tree: Tree[int] = self.query_one("#element-tree", Tree)
        groups: Dict[str, TreeNode[int]] = {}
        for index, element in enumerate(self._elements):
            group_label: str = self._entity_group_label(
                str(element.get("entity_identifier") or "")
            )
            group_node: Optional[TreeNode[int]] = groups.get(group_label)
            if group_node is None:
                group_node = tree.root.add(group_label, expand=True)
                groups[group_label] = group_node

            leaf_label: str = (
                str(element.get("title") or "").strip()
                or str(element.get("global_id") or element.get("id") or "").strip()
                or f"Element {index + 1}"
            )
            group_node.add_leaf(leaf_label, data=index)
        tree.root.expand()

    @staticmethod
    def _entity_group_label(entity_identifier: str) -> str:
        """PascalCase group label from a snake_case entity identifier.

        Groups elements by entity type — the first level of the tree — the
        same way the pre-facade-load column already available on every
        element (``entity_identifier``, e.g. ``ifc_work_schedule``) reads
        once title-cased and joined (``IfcWorkSchedule``), matching the
        facade-resolved ``entity_name`` the old single-document explorer
        showed, without needing to load any facade content just to draw
        the tree.
        """
        parts: List[str] = [part for part in entity_identifier.split("_") if part]
        return "".join(part.capitalize() for part in parts) or "Element"

    async def on_tree_node_selected(self, event: Tree.NodeSelected[int]) -> None:
        index: Optional[int] = event.node.data
        if index is None:
            return

        markdown_pane: Markdown = self.query_one("#element-markdown", Markdown)
        cached: Optional[str] = self._rendered_cache.get(index)
        if cached is not None:
            await markdown_pane.update(cached)
            return

        element: Dict[str, Any] = self._elements[index]
        rendered: Optional[str] = self._markdown_adapter.build_one(element)
        title: str = str(element.get("title") or "").strip()
        content: str = rendered or (
            f"_No facade content available for **{title or 'this element'}**._"
        )
        self._rendered_cache[index] = content
        await markdown_pane.update(content)


class StorageElementExplorerAdapter:
    """Open the standalone Textual element explorer."""

    def open(self, markdown: str) -> None:
        StorageElementExplorerApp(markdown).run()

    def open_lazy(
        self,
        elements: List[Dict[str, Any]],
        *,
        markdown_adapter: StorageElementMarkdownAdapter | None = None,
    ) -> None:
        StorageElementLazyExplorerApp(
            elements,
            markdown_adapter=markdown_adapter,
        ).run()
