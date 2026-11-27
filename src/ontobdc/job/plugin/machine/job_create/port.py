from abc import abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class JobCreateProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the creation of a job.
    """


class JobCreateStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> JobCreateProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> JobCreateProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: JobCreateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: JobCreateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: JobCreateProcessStatePort,
        to_state: JobCreateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: JobCreateProcessStatePort) -> None:
        ...
