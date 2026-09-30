from abc import ABC, abstractmethod
from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.response.command import CommandResponse


class CliCommandPort(ABC):
    """
    Port interface for CLI commands.
    """
    METADATA: "CliCommandMetadata"

    @staticmethod
    @abstractmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        ...

    @abstractmethod
    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        ...

    @abstractmethod
    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        ...
