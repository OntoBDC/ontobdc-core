from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class DictionaryInspectionProcessStatePort(str, Enum):
    """Base enum contract for dictionary inspection process states."""


class DictionaryInspectionStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DictionaryInspectionProcessStatePort:
        """Return the dictionary inspection state already reached."""
        ...


class DictionaryInspectionStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> DictionaryInspectionProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> DictionaryInspectionProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DictionaryInspectionProcessStatePort,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """Execute the dictionary inspection flow."""
        ...
