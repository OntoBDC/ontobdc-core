from abc import abstractmethod
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.loader import PluginLoaderPort
from ontobdc.shared.domain.model.health import HealthCheck


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


class PersisterCapabilityPort(CapabilityPort):
    """
    Port representing a capability that persists data through a repository.
    """
    pass


class ReadOnlyCapabilityPort(CapabilityPort):
    """
    Port representing a capability that only reads and returns data.
    """
    pass


class HealthCheckCapabilityPort(ReadOnlyCapabilityPort):
    """
    Port representing a capability that reports verifications it runs.

    Unlike the transformation family, a health check repairs nothing: it
    looks at what is there, says which verifications hold, and leaves the
    subject exactly as it found it.
    """

    @abstractmethod
    def checks(self, context: CliContextPort) -> List[HealthCheck]:
        """
        Return every verification this capability reports, in reading order.
        """
        ...
