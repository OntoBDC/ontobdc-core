from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class RemoteContainerProcessStatePort(str, Enum):
    """
    Base enum contract for remote OntoBDC Container connection states.
    """


class RemoteContainerStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> RemoteContainerProcessStatePort:
        """
        Read what is on disk and return the state the connection is already in.
        """
        ...


class RemoteContainerStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> RemoteContainerProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> RemoteContainerProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: RemoteContainerProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: RemoteContainerProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: RemoteContainerProcessStatePort,
        to_state: RemoteContainerProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: RemoteContainerProcessStatePort) -> None:
        ...
