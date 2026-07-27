
import inspect
import importlib
from typing import List, Optional, Type
from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.view.domain.port.response import ResponseMessageBoxAdapterPort


class ResponseMessageBoxAdapterLoader(PluginLoaderPort):
    def __init__(self, module_name: str = "ontobdc.view.adapter.response") -> None:
        self._module_name: str = module_name

    def get(self, response: CommandResponse) -> ResponseMessageBoxAdapterPort:
        adapter: Optional[ResponseMessageBoxAdapterPort] = self._resolve_adapter(response)

        if isinstance(adapter, ResponseMessageBoxAdapterPort):
            return adapter

        raise ValueError(f"Unsupported response type: {type(response).__name__}")

    def get_all(self) -> List[ResponseMessageBoxAdapterPort]:
        module = importlib.import_module(self._module_name)
        adapters: List[ResponseMessageBoxAdapterPort] = []
        candidate_type: Type[object]
        adapter_type: Type[ResponseMessageBoxAdapterPort]

        for _, candidate_type in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate_type, ResponseMessageBoxAdapterPort):
                continue

            if candidate_type is ResponseMessageBoxAdapterPort:
                continue

            adapter_type = candidate_type
            adapters.append(adapter_type())

        return adapters

    def _resolve_adapter(self, response: CommandResponse) -> Optional[ResponseMessageBoxAdapterPort]:
        candidates: List[ResponseMessageBoxAdapterPort] = [
            adapter for adapter in self.get_all() if adapter.accepts(response)
        ]

        if not candidates:
            return None

        candidates.sort(key=lambda adapter: self._resolve_priority(response, adapter))

        return candidates[0]

    def _resolve_priority(
        self,
        response: CommandResponse,
        adapter: ResponseMessageBoxAdapterPort,
    ) -> int:
        response_type: Type[CommandResponse] = type(response)
        candidate_type: Type[CommandResponse] = getattr(adapter, "response_type", CommandResponse)
        response_mro: List[Type[object]] = list(type(response).mro())

        if candidate_type in response_mro:
            return response_mro.index(candidate_type)

        if issubclass(response_type, candidate_type):
            return len(response_mro)

        return len(response_mro) + 1
