from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Callable, List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ContainerViewProcessStatePort(str, Enum):
    """Base enum contract for container view states."""


class ContainerViewStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[ContainerViewProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> ContainerViewProcessStatePort:
        ...


class ContainerViewStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def context(self) -> CliContextPort:
        ...

    @property
    @abstractmethod
    def target_path(self) -> Path:
        ...

    @property
    @abstractmethod
    def current_state(self) -> ContainerViewProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[ContainerViewProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ContainerViewProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: ContainerViewProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ContainerViewProcessStatePort,
        to_state: ContainerViewProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
