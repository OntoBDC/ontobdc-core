from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort


class IntentResolutionStatePort(str, Enum):
    """
    Base enum contract for run/prompt intent-resolution states.
    """


class IntentResolutionStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> IntentResolutionStatePort:
        ...

    @property
    @abstractmethod
    def process_state_class(self) -> Type[IntentResolutionStatePort]:
        ...


class IntentResolutionStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def context(self) -> CliContextPort:
        """
        Execution context used by the intent resolution flow.
        """
        ...

    @property
    @abstractmethod
    def current_state(self) -> IntentResolutionStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[IntentResolutionStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: IntentResolutionStatePort) -> bool:
        ...
