from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class FileMeaningSuggestionProcessStatePort(str, Enum):
    """
    Base enum contract for file meaning suggestion process states.
    """


class FileMeaningSuggestionStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> FileMeaningSuggestionProcessStatePort:
        """
        Read the suggestion context and return the state already reached.
        """
        ...


class FileMeaningSuggestionStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> FileMeaningSuggestionProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> FileMeaningSuggestionProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: FileMeaningSuggestionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: FileMeaningSuggestionProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: FileMeaningSuggestionProcessStatePort,
        to_state: FileMeaningSuggestionProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the file meaning suggestion flow.
        """
        ...
