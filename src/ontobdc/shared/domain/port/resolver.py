from abc import ABC, abstractmethod

from ontobdc.cli.domain.port.context import CliContextPort


class ParamResolverStrategyPort(ABC):
    """
    One resolution strategy for a family of parameter URIs.

    A strategy declares the URIs it handles instead of being selected by a
    naming convention, so adding a namespace means shipping a strategy that
    answers for it, never editing a central resolver.
    """

    @abstractmethod
    def supports(self, parameter_uri: str) -> bool:
        """
        Whether this strategy resolves the given parameter URI.
        """
        ...

    @abstractmethod
    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        """
        Resolve the parameter inside the CLI context.

        :param parameter_uri: Ontology URI declared by the capability input.
        :param parameter_name: Name of the input in the capability schema.
        """
        ...


class DynamicParamResolverPort(ABC):
    """
    Resolves a capability input declared by its ontology URI.
    """

    @abstractmethod
    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        """
        Resolve the parameter inside the CLI context.

        :param parameter_uri: Ontology URI declared by the capability input.
        :param parameter_name: Name of the input in the capability schema.
        """
        ...
