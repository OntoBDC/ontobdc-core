from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ContainerAttachProcessStatePort(str, Enum):
    """Base enum contract for storage container attach states."""


class ContainerAttachStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[ContainerAttachProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerAttachProcessStatePort:
        ...


class ContainerAttachStateTransitionHandlerPort(ABC):
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
    def current_state(self) -> ContainerAttachProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[ContainerAttachProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: ContainerAttachProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: ContainerAttachProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ContainerAttachProcessStatePort,
        to_state: ContainerAttachProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
