import shutil
from typing import Any, Dict, List, Optional, Type
import inspect
import importlib

from ontobdc.cli.adapter.suggestion import CommandSuggestionAdapter
from ontobdc.cli.domain.port.renderer import CommandResponseRendererPort
from ontobdc.cli.domain.port.response import ResponseWidgetAdapterPort
from ontobdc.shared.domain.port.loader import ResourceLoaderPort
from ontobdc.cli.domain.port.suggestion import CommandSuggestionPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.cli.domain.response.exception import ExceptionResponseBuilder


class ResponseWidgetAdapterLoader(ResourceLoaderPort):
    """Resolve OntoBDC response-to-widget adapters from the local adapter module."""

    def __init__(self, module_name: str = "ontobdc.cli.adapter.response") -> None:
        self._module_name: str = module_name

    def get(self, response: CommandResponse) -> ResponseWidgetAdapterPort:
        adapter: Optional[ResponseWidgetAdapterPort] = self._resolve_adapter(response)

        if isinstance(adapter, ResponseWidgetAdapterPort):
            return adapter

        raise ValueError(f"Unsupported response type: {type(response).__name__}")

    def get_all(self) -> List[ResponseWidgetAdapterPort]:
        module = importlib.import_module(self._module_name)
        adapters: List[ResponseWidgetAdapterPort] = []
        candidate_type: Type[object]
        adapter_type: Type[ResponseWidgetAdapterPort]

        for _, candidate_type in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate_type, ResponseWidgetAdapterPort):
                continue

            if candidate_type is ResponseWidgetAdapterPort:
                continue

            adapter_type = candidate_type
            adapters.append(adapter_type())

        return adapters

    def _resolve_adapter(
        self,
        response: CommandResponse,
    ) -> Optional[ResponseWidgetAdapterPort]:
        candidates: List[ResponseWidgetAdapterPort] = [
            adapter for adapter in self.get_all() if adapter.accepts(response)
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda adapter: self._resolve_priority(response, adapter))
        return candidates[0]

    def _resolve_priority(
        self,
        response: CommandResponse,
        adapter: ResponseWidgetAdapterPort,
    ) -> int:
        response_type: Type[CommandResponse] = type(response)
        candidate_type: Type[CommandResponse] = getattr(adapter, "response_type", CommandResponse)
        response_mro: List[Type[object]] = list(type(response).mro())

        if candidate_type in response_mro:
            return response_mro.index(candidate_type)

        if issubclass(response_type, candidate_type):
            return len(response_mro)

        return len(response_mro) + 1


class ExceptionCommandResponseLoader(ResourceLoaderPort):
    """
    Resolve a response builder from the concrete command exception type.

    Every builder in ``RESPONSE_BUILDER_MODULE`` is constructed with the
    exception and a command suggestion port, so a builder that answers an
    argument failure can offer the registered commands closest to what the
    user typed without reaching into the adapter layer itself.
    """
    RESPONSE_BUILDER_MODULE: str = "ontobdc.cli.domain.response.exception"

    def __init__(
        self,
        exception: Exception,
        suggestion: Optional[CommandSuggestionPort] = None,
    ) -> None:
        if suggestion is None:
            suggestion = CommandSuggestionAdapter()

        self._exception: Exception = exception
        self._suggestion: CommandSuggestionPort = suggestion

    def get(self) -> CommandResponse:
        """
        Build the response registered for the concrete exception type.

        Falls back to the generic builder when the type has none of its
        own, because the error path must never fail to report a failure.
        """
        try:
            response_builder_type_name: str = (
                f"{type(self._exception).__name__}ResponseBuilder"
            )
            response_builder_module: Any = importlib.import_module(
                self.RESPONSE_BUILDER_MODULE
            )
            response_builder_type: Type[Any] = ExceptionResponseBuilder
            if response_builder_type_name in vars(response_builder_module):
                response_builder_type = getattr(
                    response_builder_module,
                    response_builder_type_name,
                )

            response_builder: Any = response_builder_type(
                self._exception,
                self._suggestion,
            )

            response: CommandResponse = response_builder.build()
            return self._wrap_content_to_terminal_width(response)
        except Exception:
            response = ExceptionCommandResponse(
                description=f"Command execution failed as <{self._exception.IDENTIFIER} ({type(self._exception).__name__})>.",
                content={"error": str(self._exception)},
            )
            return self._wrap_content_to_terminal_width(response)

    def _wrap_content_to_terminal_width(
        self,
        response: CommandResponse,
    ) -> CommandResponse:
        terminal_width_size: int = shutil.get_terminal_size(
            fallback=(80, 24)
        ).columns
        content_line_width: int = terminal_width_size - 5
        wrapped_content: Dict[str, Any] = {}
        content_key: str
        content_value: Any
        for content_key, content_value in response.content.items():
            if not isinstance(content_value, str):
                wrapped_content[content_key] = content_value
                continue

            wrapped_content[content_key] = "\n".join(
                content_value[offset:offset + content_line_width]
                for offset in range(0, len(content_value), content_line_width)
            )

        response.content = wrapped_content
        return response
