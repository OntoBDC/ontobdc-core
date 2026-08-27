import json
from typing import Any, Dict, List, Optional, Tuple, Type

from ontobdc.cli.domain.port.response import ResponseWidgetAdapterPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    GraphCommandResponse,
    GridCommandResponse,
    GroupedGraphCommandResponse,
    HelpCommandResponse,
    ListCommandResponse,
    RunCommandResponse,
    TreeCommandResponse,
    WelcomeCommandResponse,
)
from ontobdc.view.component.widget.graph import GraphWidget
from ontobdc.view.component.widget.python import (
    CodeBlockWidget,
    ErrorWidget,
    GridWidget,
    KeyValueWidget,
    TableWidget,
    TextWidget,
)
from ontobdc.view.component.widget.tree import TreeWidget


class BaseResponseWidgetAdapter(ResponseWidgetAdapterPort):
    response_type: Type[CommandResponse] = CommandResponse

    def accepts(self, response: CommandResponse) -> bool:
        return isinstance(response, self.response_type)

    def widgets(self, response: CommandResponse) -> List[Any]:
        widgets: List[Any] = []

        heading_widget: Optional[TextWidget] = self._heading_widget(response)
        if heading_widget is not None:
            widgets.append(heading_widget)

        widgets.extend(self._content_widgets(response.content))
        return widgets

    def _heading_widget(self, response: CommandResponse) -> Optional[TextWidget]:
        heading: str = str(response.title).strip()
        body: str = str(response.description).strip()
        if not heading and not body:
            return None

        severity: Optional[object] = getattr(response, "severity", None)
        if severity is None:
            severity = self._default_heading_severity(response)

        return TextWidget(
            heading=heading,
            body=body,
            heading_severity=severity,
        )

    def _default_heading_severity(self, response: CommandResponse) -> Optional[object]:
        """Fallback severity badge policy applied when ``response.severity`` is unset.

        Typed subclasses keep their stronger semantics: exceptions always
        highlight as ERROR and help responses always highlight as INFO.
        Everything else — generic ``CommandResponse`` success output, list
        payloads, grouped graphs, grid payloads, welcome screens — is
        informational by default, so every command's title line carries a
        badge consistently without each command having to wire the field
        explicitly.
        """
        if isinstance(response, ExceptionCommandResponse):
            return "ERROR"
        if isinstance(response, HelpCommandResponse):
            return "INFO"
        if isinstance(response, RunCommandResponse):
            return "RUN"
        return "INFO"

    def _content_widgets(self, content: Any) -> List[Any]:
        return self._decompose(self._serialize_value(content))

    def _decompose(self, value: Any) -> List[Any]:
        """Turn one content value into widgets, recursing into dict sections.

        A dict that is not itself a flat record or a dict of same-shaped
        records is not a dead end: each of its keys becomes its own labeled
        section, decomposed the same way. This is what lets something like
        `{"Usage": [...], "Commands": {...}}` (the CLI help response) render
        as a heading + list followed by a heading + table, instead of the
        whole thing collapsing into one opaque JSON block.
        """

        if value in ({}, [], None) or value == "":
            return []

        if isinstance(value, dict):
            if self._is_harmonious_record(value):
                return [KeyValueWidget(pairs=self._record_pairs(value))]

            if self._is_dict_of_harmonious_records(value):
                return [self._dict_of_records_table(value)]

            return self._section_widgets(value)

        if isinstance(value, list):
            if self._is_harmonious_table(value):
                return [TableWidget(headers=self._table_headers(value), rows=self._table_rows(value))]

            if all(self._is_flat_cell(item) for item in value):
                return [TextWidget(body="\n".join(f"- {self._flatten_cell(item)}" for item in value))]

            return [CodeBlockWidget(text=self._to_json(value))]

        return [TextWidget(body=str(value))]

    def _section_widgets(self, sections: Dict[Any, Any]) -> List[Any]:
        widgets: List[Any] = []
        for key, value in sections.items():
            decomposed: List[Any] = self._decompose(value)
            if not decomposed:
                continue
            widgets.append(TextWidget(heading=self._format_label(key)))
            widgets.extend(decomposed)

        return widgets

    def _serialize_value(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {str(key): self._serialize_value(item) for key, item in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [self._serialize_value(item) for item in value]

        if hasattr(value, "to_dict") and callable(value.to_dict):
            return self._serialize_value(value.to_dict())

        return str(value)

    @staticmethod
    def _is_scalar(value: Any) -> bool:
        return not isinstance(value, (dict, list))

    @staticmethod
    def _is_flat_cell(value: Any) -> bool:
        """Scalar, or a list of scalars a table cell can join into one string."""

        if isinstance(value, dict):
            return False

        if isinstance(value, list):
            return all(not isinstance(item, (dict, list)) for item in value)

        return True

    @staticmethod
    def _flatten_cell(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)

        return str(value)

    def _is_harmonious_record(self, content: Dict[Any, Any]) -> bool:
        """A flat, non-empty dict of scalars reads better as a two-column table."""

        if not content:
            return False

        return all(self._is_scalar(value) for value in content.values())

    def _is_harmonious_table(self, items: List[Any]) -> bool:
        """A non-empty list of same-shaped dicts of flat cells reads better as a table."""

        if not items or not all(isinstance(item, dict) for item in items):
            return False

        first_keys: List[Any] = list(items[0].keys())
        if not first_keys:
            return False

        for item in items:
            if list(item.keys()) != first_keys:
                return False
            if not all(self._is_flat_cell(value) for value in item.values()):
                return False

        return True

    def _is_dict_of_harmonious_records(self, content: Dict[Any, Any]) -> bool:
        """A dict of >= 2 same-shaped record dicts reads better as a table.

        A single record is left to `_section_widgets` instead, since a
        one-row table reads worse than the record rendered inline.
        """

        if len(content) < 2 or not all(isinstance(value, dict) for value in content.values()):
            return False

        return self._is_harmonious_table(list(content.values()))

    def _dict_of_records_table(self, content: Dict[Any, Any]) -> TableWidget:
        inner_keys: List[Any] = list(next(iter(content.values())).keys())
        headers: List[str] = ["Key"] + [self._format_label(key) for key in inner_keys]
        rows: List[List[str]] = [
            [str(key)] + [self._flatten_cell(record[inner_key]) for inner_key in inner_keys]
            for key, record in content.items()
        ]
        return TableWidget(headers=headers, rows=rows)

    def _record_pairs(self, content: Dict[Any, Any]) -> List[Tuple[str, str]]:
        return [(self._format_label(key), str(value)) for key, value in content.items()]

    def _table_headers(self, items: List[Dict[Any, Any]]) -> List[str]:
        return [self._format_label(key) for key in items[0].keys()]

    def _table_rows(self, items: List[Dict[Any, Any]]) -> List[List[str]]:
        keys: List[Any] = list(items[0].keys())
        return [[self._flatten_cell(item[key]) for key in keys] for item in items]

    @staticmethod
    def _format_label(key: Any) -> str:
        return str(key).replace("_", " ").strip()

    @staticmethod
    def _to_json(content: Any) -> str:
        return json.dumps(content, indent=2, ensure_ascii=False)


class CommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = CommandResponse


class HelpCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = HelpCommandResponse

    def _content_widgets(self, content: Any) -> List[Any]:
        if not isinstance(content, dict):
            return super()._content_widgets(content)

        widgets: List[Any] = []
        items: List[Tuple[Any, Any]] = list(content.items())
        if not items:
            return widgets

        plain_pairs: List[Tuple[str, str]] = []
        key: Any
        value: Any
        for key, value in items:
            if isinstance(value, str) and "\n" in value.strip():
                label: str = self._format_label(key)
                if plain_pairs:
                    widgets.append(KeyValueWidget(pairs=plain_pairs))
                    plain_pairs = []
                widgets.append(TextWidget(heading=label))
                widgets.append(CodeBlockWidget(text=str(value)))
                continue
            if self._is_scalar(value):
                plain_pairs.append((self._format_label(key), str(value)))
                continue
            if plain_pairs:
                widgets.append(KeyValueWidget(pairs=plain_pairs))
                plain_pairs = []
            widgets.extend(self._section_widgets({key: value}))
        if plain_pairs:
            widgets.append(KeyValueWidget(pairs=plain_pairs))
        return widgets


class ListCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = ListCommandResponse

    def _content_widgets(self, content: Any) -> List[Any]:
        if not isinstance(content, dict):
            return super()._content_widgets(content)

        # The legacy ``rows`` list-of-label/value-dicts path is still honoured
        # for callers that build ListCommandResponse that way.  Modern lists
        # (storage containers, datasets, etc.) ship a dict with a single
        # list-valued key (``containers``, ``datasets``, …) containing
        # same-shaped flat records — those should render as a table, not as
        # section headings, otherwise the CLI paints them with the wrong
        # header casing, wrong alignment and — critically — the central
        # table renderer never sees them so the grid never spans the full
        # box width.
        rows_payload: Any = content.get("rows")
        if isinstance(rows_payload, list):
            return self._rows_widgets(rows_payload)

        list_items: List[Any]
        list_key: Optional[str] = None
        for key, value in content.items():
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                list_items = list(value)
                list_key = str(key)
                break
        else:
            return super()._content_widgets(content)

        if not self._is_harmonious_table(list_items):
            return super()._content_widgets({list_key: list_items})

        widgets: List[Any] = [TextWidget(heading=self._format_label(list_key))]
        widgets.append(
            TableWidget(
                headers=self._table_headers(list_items),
                rows=self._table_rows(list_items),
            )
        )
        return widgets

    def _rows_widgets(self, rows: List[Any]) -> List[Any]:
        pairs: List[Tuple[str, str]] = [
            (str(row.get("label", "")), str(row.get("value", "")))
            for row in rows
            if isinstance(row, dict)
        ]
        if not pairs:
            return []

        return [KeyValueWidget(pairs=pairs)]


class ExceptionCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = ExceptionCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        message: str = str(content.get("error") or response.description or "").strip()
        traceback_text: Optional[str] = str(content.get("traceback") or "").strip() or None

        return [ErrorWidget(message=message, traceback=traceback_text)]


class WelcomeCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = WelcomeCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        hero: Any = content.get("hero", "")

        return [TextWidget(body=hero if isinstance(hero, str) else "")]


class GridCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = GridCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        widgets: List[Any] = []

        heading_widget: Optional[TextWidget] = self._heading_widget(response)
        if heading_widget is not None:
            widgets.append(heading_widget)

        widgets.append(
            GridWidget(
                columns=int(content.get("columns", 1)),
                rows=int(content.get("rows", 1)),
                slot_width=int(content.get("slot_width", 20)),
                slot_height=int(content.get("slot_height", 5)),
                operation_enabled=bool(content.get("operation_enabled", False)),
                pinned_enabled=bool(content.get("pinned_enabled", False)),
            )
        )
        return widgets


class TreeCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = TreeCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        widgets: List[Any] = []

        heading_widget: Optional[TextWidget] = self._heading_widget(response)
        if heading_widget is not None:
            widgets.append(heading_widget)

        tree: Any = content.get("tree")
        widgets.append(TreeWidget(root=tree if isinstance(tree, dict) else {}))
        return widgets


class GraphCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = GraphCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        widgets: List[Any] = []

        heading_widget: Optional[TextWidget] = self._heading_widget(response)
        if heading_widget is not None:
            widgets.append(heading_widget)

        nodes: Any = content.get("nodes", [])
        edges: Any = content.get("edges", [])
        widgets.append(
            GraphWidget(
                nodes=nodes if isinstance(nodes, list) else [],
                edges=edges if isinstance(edges, list) else [],
                layout=str(content.get("layout", "force")),
                orientation=str(content.get("orientation", "default")),
            )
        )
        return widgets


class GroupedGraphCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    """Renders `GroupedGraphCommandResponse` grouped by subject instead of
    as a node-link diagram: every node that is ever an edge source gets one
    heading (its label) followed by a `predicate: object` row per outgoing
    edge — the same shape Turtle's own subject grouping produces. A node
    that is only ever an edge target (a type, a literal value, ...) never
    gets its own heading; it only shows up as a value under whichever
    subject points to it.
    """

    response_type: Type[CommandResponse] = GroupedGraphCommandResponse

    def widgets(self, response: CommandResponse) -> List[Any]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        widgets: List[Any] = []

        heading_widget: Optional[TextWidget] = self._heading_widget(response)
        if heading_widget is not None:
            widgets.append(heading_widget)

        nodes: Any = content.get("nodes", [])
        edges: Any = content.get("edges", [])
        widgets.extend(
            self._grouped_widgets(
                nodes if isinstance(nodes, list) else [],
                edges if isinstance(edges, list) else [],
            )
        )
        return widgets

    @staticmethod
    def _grouped_widgets(
        nodes: List[Dict[str, str]],
        edges: List[Dict[str, str]],
    ) -> List[Any]:
        label_by_id: Dict[str, str] = {
            str(node.get("id", "")): str(node.get("label", node.get("id", "")))
            for node in nodes
        }

        groups: Dict[str, List[Tuple[str, str]]] = {}
        for edge in edges:
            source_id: str = str(edge.get("source", ""))
            target_id: str = str(edge.get("target", ""))
            predicate_label: str = str(edge.get("label", ""))
            target_label: str = label_by_id.get(target_id, target_id)
            groups.setdefault(source_id, []).append((predicate_label, target_label))

        widgets: List[Any] = []
        for source_id, pairs in groups.items():
            subject_label: str = label_by_id.get(source_id, source_id)
            widgets.append(TextWidget(heading=subject_label))
            widgets.append(KeyValueWidget(pairs=pairs))
        return widgets
