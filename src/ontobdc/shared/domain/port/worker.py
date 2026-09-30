from abc import ABC, abstractmethod
from typing import Any, Dict


class ChainOfResponsibilityWorkerPort(ABC):
    """
    Contract for workers that execute a chain of responsibility.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the chain name.
        """
        ...

    @abstractmethod
    def work(self) -> Dict[str, Dict[str, Any]]:
        """
        Execute the chain and return each responsibility result by capability ID.
        """
        ...
