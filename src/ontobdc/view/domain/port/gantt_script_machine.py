from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class GanttScriptGenerationProcessStatePort(str, Enum):
    """Base enum contract for gantt_view runtime script generation states."""


class GanttScriptGenerationStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[GanttScriptGenerationProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> GanttScriptGenerationProcessStatePort:
        ...


class GanttScriptGenerationStateTransitionHandlerPort(ABC):
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
    def current_state(self) -> GanttScriptGenerationProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[GanttScriptGenerationProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: GanttScriptGenerationProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: GanttScriptGenerationProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: GanttScriptGenerationProcessStatePort,
        to_state: GanttScriptGenerationProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
