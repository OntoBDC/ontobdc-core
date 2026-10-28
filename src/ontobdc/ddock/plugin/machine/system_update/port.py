from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class SystemUpdateProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the update of a system.
    """


class SystemUpdateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> SystemUpdateProcessStatePort:
        """
        Return the state the update has reached.
        """
        ...


class SystemUpdateStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> SystemUpdateProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: SystemUpdateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: SystemUpdateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: SystemUpdateProcessStatePort,
        to_state: SystemUpdateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the update flow.
        """
        ...
