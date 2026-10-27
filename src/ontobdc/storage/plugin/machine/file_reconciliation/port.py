from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar


class FileReconciliationProcessStatePort(str, Enum):
    """
    Base enum contract for the file reconciliation states.
    """


class FileReconciliationRequestPort:
    """
    What the reconciliation reads from and leaves in the context, by parameter name.
    """

    # Of the request.
    CONTAINER_KEY: ClassVar[str] = "container_path"
    # Between the capabilities of a run.
    MISSING_KEY: ClassVar[str] = "reconciliation_missing"
    EXISTING_KEY: ClassVar[str] = "reconciliation_existing"
    FOUND_KEY: ClassVar[str] = "reconciliation_found"
    RELOCATED_KEY: ClassVar[str] = "reconciliation_relocated"


class FileReconciliationStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> FileReconciliationProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: FileReconciliationProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: FileReconciliationProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: FileReconciliationProcessStatePort,
        to_state: FileReconciliationProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: FileReconciliationProcessStatePort) -> None:
        ...
