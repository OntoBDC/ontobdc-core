from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ContainerRefreshProcessStatePort(str, Enum):
    """
    Base enum contract for storage container refresh states.
    """


class ContainerRefreshStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerRefreshProcessStatePort:
        """
        Read the container on disk and return the state it is already in.
        """
        ...


class ContainerRefreshStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> ContainerRefreshProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ContainerRefreshProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: ContainerRefreshProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ContainerRefreshProcessStatePort,
        to_state: ContainerRefreshProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the container refresh flow.
        """
        ...
