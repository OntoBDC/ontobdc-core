from abc import ABC, abstractmethod

from ontobdc.cli.domain.response.command import CommandResponse


class StateTransitionHandlerPort(ABC):
    """
    What a state machine handler offers to whoever composes it with another.

    A machine knows only its own states. A handler that is given another one
    to run once its own machine has reached its final state reaches it
    through this contract, and nothing else about it.
    """

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Run the machine and return what it produced.
        """
        ...
