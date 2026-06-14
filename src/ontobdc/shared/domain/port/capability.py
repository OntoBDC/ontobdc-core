
from typing import Any, Dict
from abc import abstractmethod
from ontobdc.shared.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.resource import PluginResourcePort


class CapabilityPort(PluginResourcePort):
    @abstractmethod
    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_default_cli_strategy(self, **kwargs: Any) -> Any:
        ...


class QueryCapabilityPort(CapabilityPort):
    pass


class TransformationCapabilityPort(CapabilityPort):
    pass


class TransactionCapabilityPort(CapabilityPort):
    pass