
from dataclasses import dataclass
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from ontobdc.cli.domain.resource.command import CommandResponse


@dataclass
class CliCommandMetadata:
    id: str
    logical_component: str
    description: str = ""
    arguments: List[Dict[str, Any]] = None


class CliCommandPort(ABC):
    """
    Port interface for CLI commands.
    """
    METADATA: CliCommandMetadata

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
