
from dataclasses import dataclass
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from ontobdc.cli.domain.response.command import CommandResponse


@dataclass
class CliCommandMetadata:
    id: str
    logical_component: str
    description: str = ""
    usage: str = ""
    arguments: List[Dict[str, Any]] = None
    depends_on: List[str] | str = "DEFAULT"

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = []
            
        if self.depends_on == "DEFAULT":
            self.depends_on = ["cli.is_root_dir_set"]
        elif self.depends_on is None:
            self.depends_on = []



class CliCommandPort(ABC):
    """
    Port interface for CLI commands.
    """
    METADATA: CliCommandMetadata

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
