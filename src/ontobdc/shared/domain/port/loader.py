from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Type

from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort


class RootPackagesAwarePort(ABC):
    """
    Port for classes that discover plugins and must be told where to look.

    An executable that reuses this runtime discovers its own plugins under
    its own package. A collaborator that loads plugins of its own, rather
    than being handed them, would otherwise search only the package this
    runtime lives in, and never find the other executable's.
    """

    @abstractmethod
    def set_root_packages(self, root_packages: Tuple[str, ...]) -> None:
        """
        Tell the implementing class which packages to discover plugins in.
        """
        ...


class PluginLoaderPort(ABC):
    """
    Base port interface for dynamic plugin loaders.
    """
    pass


class ResourceLoaderPort(ABC):
    """
    Base port interface for dynamic resource loaders.
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


class ResolverLoaderPort(PluginLoaderPort):
    """
    Contract for parameter resolver strategy loaders.
    """
    @abstractmethod
    def get_all(self, resource: str = "resolver") -> List[Type["ParamResolverStrategyPort"]]:
        """
        Retrieve every parameter resolver strategy shipped by the plugins.
        """
        ...


class ChainResponsibilityLoaderPort(PluginLoaderPort):
    """
    Contract for discovering capabilities that support a chain contract.
    """

    @abstractmethod
    def get(
        self,
        support: Type[ChainResponsibilityPort],
        id: str,
    ) -> Optional[Type[object]]:
        """
        Retrieve one capability supporting ``support`` by capability ID.
        """
        ...

    @abstractmethod
    def get_all(
        self,
        support: Type[ChainResponsibilityPort],
        resource: str = "capability",
    ) -> List[Type[object]]:
        """
        Retrieve every capability implementing the requested support contract.
        """
        ...
