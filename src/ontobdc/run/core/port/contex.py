
from typing import Any, Dict, List
from abc import ABC, abstractmethod


class CliContextPort(ABC):

    @property
    @abstractmethod
    def raw_args(self) -> List[str]:
        ...

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Dict[str, Any]]:
        ...

    @property
    @abstractmethod
    def unprocessed_args(self) -> List[str]:
        ...

    @property
    @abstractmethod
    def is_capability_targeted(self) -> bool:
        """
        Returns True if a specific capability was targeted (via --id).
        """
        ...

    @property
    @abstractmethod
    def target_capability_id(self) -> str | None:
        """
        Returns the targeted capability ID if specified, None otherwise.
        """
        ...

    @property
    @abstractmethod
    def root_path(self) -> str:
        """
        Returns the root path of the repository.
        """
        ...

    @abstractmethod
    def add_parameter(self, param_key: str, param_value: Dict[str, Any]):
        ...
        
    @abstractmethod
    def get_parameter_value(self, param_key: str) -> Any:
        """
        Retrieves the 'value' of a parameter by its key.
        Returns None if parameter does not exist.
        """
        ...

    @abstractmethod
    def clear_parameters(self, param_keys: List[str]) -> None:
        ...


class CliContextStrategyPort(ABC):
    @abstractmethod
    def execute(self, context: CliContextPort) -> CliContextPort:
        ...