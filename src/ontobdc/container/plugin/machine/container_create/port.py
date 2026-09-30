from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ContainerCreateProcessStatePort(str, Enum):
    """
    Base enum contract for storage container creation states.
    """


class ContainerCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerCreateProcessStatePort:
        """
        Read the container on disk and return the state it is already in.
        """
        ...


class ContainerCreateStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> ContainerCreateProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ContainerCreateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: ContainerCreateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ContainerCreateProcessStatePort,
        to_state: ContainerCreateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the container creation flow.
        """
        ...


class DatasetCreateProcessStatePort(str, Enum):
    """
    Base enum contract for storage dataset creation states.
    """
