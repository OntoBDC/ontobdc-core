
from abc import abstractmethod
from typing import Any, List
from ontobdc.shared.domain.port.machine import (
    ProcessStatePort,
    StateEvaluatorPort,
    StateTransitionHandlerPort,
    StatechartRepositoryPort,
)


class EtlProcessStatePort(ProcessStatePort):
    """
    Enum representing the possible states of the ETL process.
    """
    pass


class EtlStatechartRepositoryPort(StatechartRepositoryPort):
    """
    Contract for retrieving the A3 ETL statechart definition.
    """

    @abstractmethod
    def get_statechart(self) -> Any:
        ...


class EtlStateEvaluatorPort(StateEvaluatorPort):
    """
    Contract for evaluating the current state of an A3 ETL execution.
    """

    @abstractmethod
    def evaluate(self, context: Any) -> EtlProcessStatePort:
        ...


class EtlStateTransitionHandlerPort(StateTransitionHandlerPort):
    """
    Contract for handling state transitions within the A3 ETL pipeline.
    """

    @property
    @abstractmethod
    def current_state(self) -> EtlProcessStatePort:
        ...

    @property
    @abstractmethod
    def transitions(self) -> List[Any]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: EtlProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: EtlProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(self, from_state: EtlProcessStatePort, to_state: EtlProcessStatePort) -> bool:
        ...

    @abstractmethod
    def system_checks_passed(self) -> bool:
        ...

    @abstractmethod
    def has_error(self) -> bool:
        ...
