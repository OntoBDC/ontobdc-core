from abc import abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class CliInitAddonProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the process that adds an addon.
    """


class CliInitAddonStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> CliInitAddonProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> CliInitAddonProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: CliInitAddonProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: CliInitAddonProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: CliInitAddonProcessStatePort,
        to_state: CliInitAddonProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: CliInitAddonProcessStatePort) -> None:
        ...
