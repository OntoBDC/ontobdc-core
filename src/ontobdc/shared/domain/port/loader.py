
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Type

if TYPE_CHECKING:
    from ontobdc.cli.domain.port.command import CliCommandPort
    from ontobdc.cli.domain.port.logger import LogRepositoryPort


class PluginLoaderPort(ABC):
    """
    Base port interface for dynamic plugin loaders.
    """
    pass


class CommandLoaderPort(PluginLoaderPort):
    """
    Contract for command plugin loaders.
    """
    @abstractmethod
    def __init__(self, logical_component: str, logger: "LogRepositoryPort"):
        """
        Build a command loader for the given logical component.
        """
        ...

    @abstractmethod
    def get(self, id: str) -> Type["CliCommandPort"]:
        """
        Retrieve a command plugin by its ID.
        """
        ...

    @abstractmethod
    def get_all(self, resource: str = "command") -> List[Type["CliCommandPort"]]:
        """
        Retrieve all command plugins for the configured logical component.
        """
        ...
