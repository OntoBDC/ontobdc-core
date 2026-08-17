from abc import ABC, abstractmethod
from typing import Any, List

from ontobdc.cli.domain.response.command import CommandResponse


class ResponseWidgetAdapterPort(ABC):
    @abstractmethod
    def accepts(self, response: CommandResponse) -> bool:
        """
        Check whether this adapter supports the given response.
        """
        ...

    @abstractmethod
    def widgets(self, response: CommandResponse) -> List[Any]:
        """
        Decompose the response into the content payloads that materialize it.

        The returned list may contain :class:`ontobdc.view.domain.port.widget.Widget`
        subclasses (for fallbacks that still self-render) as well as plain
        dataclass containers such as ``TableWidget``/``KeyValueWidget``/
        ``ErrorWidget`` that are rendered by the central presentation layer.
        """
        ...
