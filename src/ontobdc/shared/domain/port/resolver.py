
from abc import ABC, abstractmethod
from ontobdc.shared.domain.port.context import CliContextPort


class CapabilityParamResolverRunnerPort(ABC):
    @abstractmethod
    def resolve(self, context: CliContextPort, prop_uri: str, prop_value: str) -> None:
        ...
