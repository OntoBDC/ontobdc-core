
from enum import Enum
from typing import List, Any
from abc import ABC, abstractmethod


class ProcessStatePort(str, Enum):
    """
    Enum representing the possible states of the process.
    """
    pass


class StatechartRepositoryPort(ABC):
    """
    Contract for retrieving the statechart definition.
    """
    @abstractmethod
    def get_statechart(self) -> Any:
        """
        Returns the parsed statechart object. 
        Typed as Any to avoid coupling domain ports to the Sismic library.
        """
        pass


class StateEvaluatorPort(ABC):
    """
    Contract for evaluating the current state from the execution context.
    """
    @abstractmethod
    def evaluate(self, context: Any) -> ProcessStatePort:
        """
        Determines the current state based on the available execution context.
        """
        pass


class StateTransitionHandlerPort(ABC):
    """
    Contract for handling state transitions within the A3 pipeline.
    This interface is expected by the Sismic state machine via the 'handler' alias.
    """

    @property
    @abstractmethod
    def current_state(self) -> ProcessStatePort:
        """
        Gets the current evaluated state of the physical package.
        """
        ...

    @property
    @abstractmethod
    def transitions(self) -> List[Any]:
        """
        Gets the list of available transitions (usually injected by Sismic).
        """
        ...

    @property
    @abstractmethod
    def is_successful(self) -> bool:
        """
        Indicates if the current state is successful.
        """
        ...

    @property
    @abstractmethod
    def is_unresolvable(self) -> bool:
        """
        Indicates if the current state is unresolvable.
        """
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ProcessStatePort) -> bool:
        """
        Checks if a transition to the target state is allowed based on the current physical state.
        
        :param to_state: Target state
        :return: True if transition is allowed
        """
        pass

    @abstractmethod
    def perform_state_transition(self, to_state: ProcessStatePort) -> None:
        """
        Executes the business logic (Use Case) to actually perform the state transition.
        
        :param to_state: Target state
        """
        pass

    @abstractmethod
    def validate_state_transition(self, from_state: ProcessStatePort, to_state: ProcessStatePort) -> bool:
        """
        Validates if a transition between two states was successful or is logically valid.
        
        :param from_state: Source state
        :param to_state: Target state
        :return: True if transition is valid
        """
        pass
