from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class EntityInspectionProcessStatePort(str, Enum):
    """Base enum contract for entity inspection process states."""


class EntityInspectionStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> EntityInspectionProcessStatePort:
        """Return the entity inspection state already reached."""
        ...


class EntityInspectionStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> EntityInspectionProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> EntityInspectionProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: EntityInspectionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: EntityInspectionProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: EntityInspectionProcessStatePort,
        to_state: EntityInspectionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """Execute the entity inspection flow."""
        ...
