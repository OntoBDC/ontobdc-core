from abc import ABC, abstractmethod
from typing import List

from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.view.domain.port.widget import Widget


class ResponseWidgetAdapterPort(ABC):
    @abstractmethod
    def accepts(self, response: CommandResponse) -> bool:
        """
        Check whether this adapter supports the given response.
        """
        ...

    @abstractmethod
    def widgets(self, response: CommandResponse) -> List[Widget]:
        """
        Decompose the response into the Widgets that materialize it.
        """
        ...
