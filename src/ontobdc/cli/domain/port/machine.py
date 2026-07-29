
from enum import Enum
from typing import List, Type
from abc import ABC, abstractmethod

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class CliInitProcessStatePort(str, Enum):
    """
    Base enum contract for CLI init process states.
    """
    @abstractmethod
    def label(self, lang: str = "en") -> str:
        ...

    @abstractmethod
    def description(self, lang: str = "en") -> str:
        ...

    @staticmethod
    @abstractmethod
    def get_state(state: str) -> "CliInitProcessStatePort":
        ...


class CliInitStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> CliInitProcessStatePort:
        ...

    @property
    @abstractmethod
    def process_state_class(self) -> Type[CliInitProcessStatePort]:
        ...


class CliInitStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> CliInitProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[CliInitProcessStatePort]:
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
    def execute(self) -> CommandResponse:
        ...
