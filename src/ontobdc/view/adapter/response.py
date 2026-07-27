
import json
import traceback
from abc import ABC
from typing import Any, Dict, List, Optional, Type
from ontobdc.view.domain.port.layout import MessageBoxLayoutRendererPort
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    HelpCommandResponse,
    ListCommandResponse,
)
from ontobdc.view.domain.port.response import MessageBoxLayoutData, ResponseMessageBoxAdapterPort


class BaseCommandResponseMessageBoxHelper(ABC):
    response_type: Type[CommandResponse] = CommandResponse
    color: str = "GRAY"
    title_type: str = "OntoBDC"

    def accepts(self, response: CommandResponse) -> bool:
        return isinstance(response, self.response_type)

    def map(self, response: CommandResponse) -> MessageBoxLayoutData:
        return MessageBoxLayoutData(
            title_type=self._resolve_title_type(response),
            color=self._resolve_color(response),
            title=self._resolve_title(response),
            partial=self._resolve_partial(response),
            content=self._resolve_content(response),
            subtitle=self._resolve_subtitle(response),
            footer=self._resolve_footer(response),
        )

    def render(self, response: CommandResponse, layout: MessageBoxLayoutRendererPort) -> str:
        return layout.render(self.map(response))

    def _resolve_title_type(self, response: CommandResponse) -> str:
        _ = response
        return self.title_type

    def _resolve_child_content(self, content: Any, level: int = 3) -> str:
        _ = level
        return self._join_lines(self._format_markdown_block(content))

    def _serialize_response_content(self, content: Any) -> str:
        normalized_content: Any = self._normalize_content(content)
        if isinstance(normalized_content, dict):
            md_content: str = ""
            for key, item in normalized_content.items():
                md_content += f"## {self._format_section_title(key)}\n"
                md_content += self._join_lines(self._format_markdown_block(item))
                md_content += "\n"

            return md_content.rstrip()

        if isinstance(normalized_content, list):
            return self._join_lines(self._format_markdown_block(normalized_content))

        return str(content)

    def _normalize_content(self, content: Any) -> Any:
        if isinstance(content, dict):
            return content

        if isinstance(content, (list, tuple, set)):
            return list(content)

        if not isinstance(content, str):
            return content

        stripped_content: str = content.strip()
        if not stripped_content:
            return content

        try:
            parsed_content: Any = json.loads(stripped_content)
        except (json.decoder.JSONDecodeError, TypeError):
            return content

        if isinstance(parsed_content, tuple):
            return list(parsed_content)

        return parsed_content

    def _stringify_scalar(self, content: Any) -> str:
        if isinstance(content, str):
            return content

        return str(content)

    def _format_markdown_block(self, content: Any, indent: int = 0) -> List[str]:
        normalized_content: Any = self._normalize_content(content)

        if isinstance(normalized_content, dict):
            return self._format_dict_block(normalized_content, indent)

        if isinstance(normalized_content, list):
            return self._format_list_block(normalized_content, indent)

        return [f"{self._indent(indent)}{self._stringify_scalar(normalized_content)}"]

    def _format_dict_block(self, content: Dict[Any, Any], indent: int) -> List[str]:
        lines: List[str] = []

        for key, value in content.items():
            label: str = self._format_label(key)
            normalized_value: Any = self._normalize_content(value)

            if self._is_scalar(normalized_value):
                lines.append(f"{self._indent(indent)}- {label}: {self._stringify_scalar(normalized_value)}")
                continue

            lines.append(f"{self._indent(indent)}- {label}:")
            lines.extend(self._format_markdown_block(normalized_value, indent + 1))

        return lines

    def _format_list_block(self, content: List[Any], indent: int) -> List[str]:
        lines: List[str] = []

        for index, item in enumerate(content):
            normalized_item: Any = self._normalize_content(item)

            if isinstance(normalized_item, dict):
                lines.extend(self._format_list_dict_item(normalized_item, indent))
            elif isinstance(normalized_item, list):
                lines.append(f"{self._indent(indent)}-")
                lines.extend(self._format_markdown_block(normalized_item, indent + 1))
            else:
                lines.append(f"{self._indent(indent)}- {self._stringify_scalar(normalized_item)}")

            if index < len(content) - 1 and isinstance(normalized_item, dict):
                lines.append("")

        return lines

    def _format_list_dict_item(self, content: Dict[Any, Any], indent: int) -> List[str]:
        lines: List[str] = []
        preferred_key: Optional[str] = self._resolve_preferred_item_key(content)

        if preferred_key is not None:
            preferred_value: Any = self._normalize_content(content[preferred_key])
            lines.append(
                f"{self._indent(indent)}- {self._format_label(preferred_key)}: "
                f"{self._stringify_scalar(preferred_value)}"
            )

            for key, value in content.items():
                if key == preferred_key:
                    continue

                label: str = self._format_label(key)
                normalized_value: Any = self._normalize_content(value)
                if self._is_scalar(normalized_value):
                    lines.append(
                        f"{self._indent(indent + 1)}- {label}: {self._stringify_scalar(normalized_value)}"
                    )
                    continue

                lines.append(f"{self._indent(indent + 1)}- {label}:")
                lines.extend(self._format_markdown_block(normalized_value, indent + 2))

            return lines

        lines.append(f"{self._indent(indent)}-")
        lines.extend(self._format_dict_block(content, indent + 1))
        return lines

    def _resolve_preferred_item_key(self, content: Dict[Any, Any]) -> Optional[str]:
        preferred_keys: List[str] = ["repository", "name", "id", "title", "file", "path", "branch"]

        for preferred_key in preferred_keys:
            if preferred_key not in content:
                continue

            preferred_value: Any = self._normalize_content(content[preferred_key])
            if self._is_scalar(preferred_value):
                return preferred_key

        return None

    def _format_section_title(self, key: Any) -> str:
        return self._format_label(key).title()

    def _format_label(self, key: Any) -> str:
        return str(key).replace("_", " ").strip()

    def _indent(self, indent: int) -> str:
        return "  " * indent

    def _is_scalar(self, content: Any) -> bool:
        return not isinstance(content, (dict, list))

    def _join_lines(self, lines: List[str]) -> str:
        return "\n".join(lines).rstrip() + ("\n" if len(lines) > 0 else "")

    def _resolve_color(self, response: CommandResponse) -> str:
        _ = response
        return self.color

    def _resolve_title(self, response: CommandResponse) -> str:
        return response.title

    def _resolve_partial(self, response: CommandResponse) -> str:
        return response.title

    def _resolve_content(self, response: CommandResponse) -> str:
        return f"{response.description}\n\n{self._serialize_response_content(response.content)}"

    def _resolve_subtitle(self, response: CommandResponse) -> Optional[str]:
        return f"{response.subtitle}"

    def _resolve_subtitle(self, response: CommandResponse) -> Optional[str]:
        _ = response
        return None

    def _resolve_footer(self, response: CommandResponse) -> Optional[str]:
        _ = response
        return None


class CommandResponseMessageBoxAdapter(
    BaseCommandResponseMessageBoxHelper,
    ResponseMessageBoxAdapterPort
):
    response_type: Type[CommandResponse] = CommandResponse
    color: str = "GRAY"


class ExceptionCommandResponseMessageBoxAdapter(
    BaseCommandResponseMessageBoxHelper,
    ResponseMessageBoxAdapterPort
):
    response_type: Type[CommandResponse] = ExceptionCommandResponse
    color: str = "RED"
    title_type: str = "ERROR"

    def _serialize_response_content(self, content: Any) -> str:
        response: str = super()._serialize_response_content(content)
        if isinstance(content, dict) and "error" in content.keys():
            response = f"\033[37mDETAILS\033[90m\n  {content['error']}"

        response = f"{response}\n\n\033[37mTRACEBACK\033[90m\n  {traceback.format_exc()}"

        return response


class HelpCommandResponseMessageBoxAdapter(
    BaseCommandResponseMessageBoxHelper,
    ResponseMessageBoxAdapterPort
):
    response_type: Type[CommandResponse] = HelpCommandResponse
    color: str = "GRAY"


class ListCommandResponseMessageBoxAdapter(
    BaseCommandResponseMessageBoxHelper,
    ResponseMessageBoxAdapterPort
):
    response_type: Type[CommandResponse] = ListCommandResponse
    color: str = "CYAN"


class CommandResponseMessageBoxDataResolverAdapter:
    def __init__(self, adapters: List[ResponseMessageBoxAdapterPort]) -> None:
        self._adapters: List[ResponseMessageBoxAdapterPort] = adapters

    def map(self, response: CommandResponse) -> MessageBoxLayoutData:
        adapter: ResponseMessageBoxAdapterPort = self._resolve_adapter(response)
        return adapter.map(response)

    def _resolve_adapter(self, response: CommandResponse) -> ResponseMessageBoxAdapterPort:
        adapter: ResponseMessageBoxAdapterPort

        for adapter in self._adapters:
            if adapter.accepts(response):
                return adapter

        raise ValueError(f"Unsupported response type: {type(response).__name__}")
