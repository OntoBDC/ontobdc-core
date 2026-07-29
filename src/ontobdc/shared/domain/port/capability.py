
from typing import Any, Dict
from abc import ABC, abstractmethod
from ontobdc.shared.facade.port.context import CliContextPort
from ontobdc.shared.domain.port.loader import PluginLoaderPort


class CapabilityPort(PluginLoaderPort):
    """
    Base port interface for all capabilities executable by the CLI or application contexts.
    """
    @abstractmethod
    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Executes the capability using the provided CLI context.
        """
        ...

    @abstractmethod
    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        """
        Returns the default CLI execution strategy associated with this capability.
        """
        ...


class QueryCapabilityPort(CapabilityPort):
    """
    Port representing a capability designed to query information without side effects.
    """
    pass


class TransformationCapabilityPort(CapabilityPort):
    """
    Port representing a capability designed to transform data structures.
    """
    pass


class TransactionCapabilityPort(CapabilityPort):
    """
    Port representing a capability that modifies state or performs transactions.
    """
    pass


class EntityQueryCapabilityVisitablePort(ABC):
    """
    Port for capabilities that can accept visitors.
    """
    @abstractmethod
    def accept(self, visitor: 'RemoteDatasetCapabilityVisitorPort') -> Any:
        """
        Accept a visitor and return the result.
        """
        ...


