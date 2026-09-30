from abc import ABC, abstractmethod
from typing import Any, List

from ontobdc.cli.domain.response.command import CommandResponse


class ResponseWidgetLoaderPort(ABC):
    """
    Port for the collaborator that decomposes a response into widgets.
    """
    @abstractmethod
    def widgets(self, response: CommandResponse) -> List[Any]:
        """
        Return the widget payloads that materialize the given response.
        """
        ...


class TerminalSurfacePort(ABC):
    """
    Port for the terminal presentation surface that frames a markdown body.
    """
    @abstractmethod
    def render(self, body_markdown: str, theme: str) -> str:
        """
        Frame the markdown body with the given UX theme and return the output.
        """
        ...


class TerminalStylePort(ABC):
    """
    Port for the terminal styling applied to severities and detail lines.
    """
    @abstractmethod
    def badge(self, severity: str) -> str:
        """
        Return the badge that prefixes a heading for the given severity.
        """
        ...

    @abstractmethod
    def dim(self, text: str) -> str:
        """
        Return the text rendered as a secondary, de-emphasized line.
        """
        ...


class CommandResponseRendererPort(ABC):
    """
    Port for rendering a command response in a single output mode.
    """
    @abstractmethod
    def render(self, response: CommandResponse, render_type: str) -> None:
        """
        Render the response to the console in the requested output mode.
        """
        ...
