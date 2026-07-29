
from abc import ABC, abstractmethod
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.view.domain.port.layout import MessageBoxLayoutData, MessageBoxLayoutRendererPort


class ResponseMessageBoxRendererPort(ABC):
    @abstractmethod
    def render(self, response: CommandResponse, layout: MessageBoxLayoutRendererPort) -> str:
        ...


class ResponseMessageBoxAdapterPort(ResponseMessageBoxRendererPort, ABC):
    @abstractmethod
    def accepts(self, response: CommandResponse) -> bool:
        ...

    @abstractmethod
    def map(self, response: CommandResponse) -> MessageBoxLayoutData:
        ...

    @abstractmethod
    def render(self, response: CommandResponse, layout: MessageBoxLayoutRendererPort) -> str:
        ...
