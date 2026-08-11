from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class SurfaceGenerationProcessStatePort(str, Enum):
    """Base enum contract for offline HTML Surface generation states."""


class SurfaceGenerationStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[SurfaceGenerationProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> SurfaceGenerationProcessStatePort:
        ...


class SurfaceGenerationStateTransitionHandlerPort(ABC):
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
    def current_state(self) -> SurfaceGenerationProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[SurfaceGenerationProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: SurfaceGenerationProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: SurfaceGenerationProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: SurfaceGenerationProcessStatePort,
        to_state: SurfaceGenerationProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
