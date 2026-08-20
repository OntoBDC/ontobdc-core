from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class WorkStreamScriptGenerationProcessStatePort(str, Enum):
    """Base enum contract for work_stream_view runtime script generation states."""


class WorkStreamScriptGenerationStateEvaluatorPort(ABC):
    @property
    @abstractmethod
    def process_state_class(self) -> Type[WorkStreamScriptGenerationProcessStatePort]:
        ...

    @abstractmethod
    def evaluate(self, context: CliContextPort) -> WorkStreamScriptGenerationProcessStatePort:
        ...


class WorkStreamScriptGenerationStateTransitionHandlerPort(ABC):
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
    def current_state(self) -> WorkStreamScriptGenerationProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[WorkStreamScriptGenerationProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: WorkStreamScriptGenerationProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: WorkStreamScriptGenerationProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: WorkStreamScriptGenerationProcessStatePort,
        to_state: WorkStreamScriptGenerationProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        ...
