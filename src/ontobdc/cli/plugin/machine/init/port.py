from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class CliInitProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the CLI init process.
    """


class CliInitStateEvaluatorPort(ABC):
    """
    Reads the container on disk and reports the state it is already in.
    """

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> CliInitProcessStatePort:
        ...


class CliInitStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> CliInitProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> CliInitProcessStatePort:
        ...

    @property
    @abstractmethod
    def next_handler(self) -> Optional[StateTransitionHandlerPort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: CliInitProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: CliInitProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: CliInitProcessStatePort,
        to_state: CliInitProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: CliInitProcessStatePort) -> None:
        ...
