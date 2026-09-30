from typing import List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.loader import ResolverLoaderPort
from ontobdc.shared.domain.port.resolver import (
    DynamicParamResolverPort,
    ParamResolverStrategyPort,
)
from ontobdc.shared.domain.exception.resolver import (
    ParamResolverStrategyNotFoundError,
)


class UnresolvedParamResolver(DynamicParamResolverPort):
    """
    Resolver that deliberately resolves nothing.

    It is the default composition wherever parameter resolution is not wired
    yet, and it says so in its name: an input declaring a URI is left exactly
    as the context already holds it.
    """

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        """
        Leave the parameter untouched.
        """
        return None


class StrategyParamResolver(DynamicParamResolverPort):
    """
    Resolver that delegates to the discovered strategy supporting the URI.

    Selection asks each strategy whether it supports the URI, so namespaces
    are owned by the strategies that answer for them rather than by a list
    kept in this class. Strategies come from an injected loader; nothing here
    touches the filesystem, a module name, or a class name.
    """

    def __init__(self, loader: ResolverLoaderPort) -> None:
        self._loader: ResolverLoaderPort = loader
        self._strategies: Optional[List[ParamResolverStrategyPort]] = None

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        """
        Resolve the parameter through the first strategy that supports its URI.

        :raises ParamResolverStrategyNotFoundError: No strategy answers for
            the URI, which means the plugin owning it is missing.
        """
        strategy: ParamResolverStrategyPort
        for strategy in self._available_strategies():
            if strategy.supports(parameter_uri):
                strategy.resolve(context, parameter_uri, parameter_name)
                return

        raise ParamResolverStrategyNotFoundError(parameter_uri, parameter_name)

    def _available_strategies(self) -> List[ParamResolverStrategyPort]:
        """
        Instantiate the discovered strategies once per resolver.
        """
        if self._strategies is None:
            self._strategies = [
                strategy_type()
                for strategy_type in self._loader.get_all()
            ]

        return self._strategies
