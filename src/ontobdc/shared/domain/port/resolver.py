
from abc import ABC, abstractmethod
from ontobdc.shared.facade.port.context import CliContextPort


class DynamicParamResolverPort(ABC):
    """
    Port interface defining a dynamic resolver for CLI context parameters based on their ontology URI.
    """
    @abstractmethod
    def resolve(self, context: CliContextPort, prop_uri: str, prop_value: str) -> None:
        """
        Dynamically resolves the parameter value inside the CLI context.
        """
        ...