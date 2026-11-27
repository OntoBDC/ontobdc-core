from abc import abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort


class ActionDatesCatalogProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the cataloging of the dates of the actions in a container.
    """


class ActionDatesCatalogStateTransitionHandlerPort(StateTransitionHandlerPort):
    @property
    @abstractmethod
    def current_state(self) -> ActionDatesCatalogProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> ActionDatesCatalogProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ActionDatesCatalogProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: ActionDatesCatalogProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ActionDatesCatalogProcessStatePort,
        to_state: ActionDatesCatalogProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def bind_active_state(self, state: ActionDatesCatalogProcessStatePort) -> None:
        ...
