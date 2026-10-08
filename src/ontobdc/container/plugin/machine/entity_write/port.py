from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class EntityWriteProcessStatePort(str, Enum):
    """
    Base enum contract for entity writing states.
    """


class EntityWriteStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> EntityWriteProcessStatePort:
        """
        Read the dataset and its data source and return the state the entity writing is already in.
        """
        ...


class EntityWriteStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> EntityWriteProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: EntityWriteProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: EntityWriteProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: EntityWriteProcessStatePort,
        to_state: EntityWriteProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the entity writing flow.
        """
        ...
