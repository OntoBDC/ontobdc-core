from typing import ClassVar

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.resolver import ParamResolverStrategyPort
from ontobdc.container.plugin.parameter.container import ContainerIdStrategy


class ContainerIdResolverStrategy(ParamResolverStrategyPort):
    """
    Resolves the container a capability declares as an input.

    A capability names what it needs by URI, never how to obtain it. This
    strategy answers for the container identifier URI and delegates the
    obtaining to ContainerIdStrategy, the same resolution the parameter stage
    runs for commands: an explicit selector when one was given, the current
    working directory otherwise.
    """

    CONTAINER_ID_URI: ClassVar[str] = "org.ontobdc.storage.container.id"

    def supports(self, parameter_uri: str) -> bool:
        """
        Whether this strategy resolves the given parameter URI.
        """
        return parameter_uri.strip() == self.CONTAINER_ID_URI

    def resolve(
        self,
        context: CliContextPort,
        parameter_uri: str,
        parameter_name: str,
    ) -> None:
        """
        Bind the resolved container identifier and path into the context.
        """
        ContainerIdStrategy().execute(context)
