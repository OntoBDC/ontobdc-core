from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class DatasetCreateProcessStatePort(str, Enum):
    """
    Base enum contract for storage dataset creation states.
    """


class DatasetCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DatasetCreateProcessStatePort:
        """
        Read the dataset on disk and return the state it is already in.
        """
        ...


class DatasetCreateStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> DatasetCreateProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: DatasetCreateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: DatasetCreateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DatasetCreateProcessStatePort,
        to_state: DatasetCreateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the dataset creation flow.
        """
        ...
