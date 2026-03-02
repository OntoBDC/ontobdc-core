from abc import abstractmethod
from typing import Any, Dict, Protocol, runtime_checkable

@runtime_checkable
class SelfVerifiablePort(Protocol):
    """
    Interface for components that can verify their own integrity or input validity.
    """
    @abstractmethod
    def check_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Self-verification of inputs.
        
        Args:
            inputs: The input dictionary to be verified.
            
        Returns:
            bool: True if inputs are valid, False otherwise.
        """
        ...


@runtime_checkable
class VerificationStrategyPort(Protocol):
    """
    Interface for external verification strategies.
    Allows injecting complex validation logic (e.g., checking external services, databases).
    """
    @abstractmethod
    def verify(self, input_key: str, input_value: Any, inputs: Dict[str, Any]) -> bool:
        """
        Verifies if inputs are valid according to this strategy.
        
        Args:
            input_key: The key of the input to be verified.
            input_value: The value of the input to be verified.
            
        Returns:
            bool: True if inputs are valid, False otherwise.
        """
        ...
