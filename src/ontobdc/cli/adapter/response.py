import json
from typing import Any, Dict, List, Optional, Tuple, Type

from ontobdc.cli.domain.port.response import ResponseWidgetAdapterPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    GridCommandResponse,
    HelpCommandResponse,
    ListCommandResponse,
    WelcomeCommandResponse,
)
from ontobdc.view.component.widget.python import (
    CodeBlockWidget,
    ErrorWidget,
    GridWidget,
    KeyValueWidget,
    TableWidget,
    TextWidget,
)
from ontobdc.view.domain.port.widget import Widget


class BaseResponseWidgetAdapter(ResponseWidgetAdapterPort):
    response_type: Type[CommandResponse] = CommandResponse

    def accepts(self, response: CommandResponse) -> bool:
        return isinstance(response, self.response_type)

    def widgets(self, response: CommandResponse) -> List[Widget]:
        widgets: List[Widget] = []

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

        return TextWidget(heading=heading, body=body)

    def _content_widgets(self, content: Any) -> List[Widget]:
        return self._decompose(self._serialize_value(content))

    def _decompose(self, value: Any) -> List[Widget]:
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

    def _section_widgets(self, sections: Dict[Any, Any]) -> List[Widget]:
        widgets: List[Widget] = []
        for key, value in sections.items():
            widgets.append(TextWidget(heading=self._format_label(key)))
            widgets.extend(self._decompose(value))

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


class ListCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = ListCommandResponse

    def _content_widgets(self, content: Any) -> List[Widget]:
        if isinstance(content, dict) and isinstance(content.get("rows"), list):
            return self._rows_widgets(content["rows"])

        return super()._content_widgets(content)

    def _rows_widgets(self, rows: List[Any]) -> List[Widget]:
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

    def widgets(self, response: CommandResponse) -> List[Widget]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        message: str = str(content.get("error") or response.description or "").strip()
        traceback_text: Optional[str] = str(content.get("traceback") or "").strip() or None

        return [ErrorWidget(message=message, traceback=traceback_text)]


class WelcomeCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = WelcomeCommandResponse

    def widgets(self, response: CommandResponse) -> List[Widget]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        hero: Any = content.get("hero", "")

        return [TextWidget(body=hero if isinstance(hero, str) else "")]


class GridCommandResponseWidgetAdapter(BaseResponseWidgetAdapter):
    response_type: Type[CommandResponse] = GridCommandResponse

    def widgets(self, response: CommandResponse) -> List[Widget]:
        content: Dict[str, Any] = response.content if isinstance(response.content, dict) else {}
        widgets: List[Widget] = []

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
