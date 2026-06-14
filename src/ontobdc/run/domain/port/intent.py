
from abc import ABC, abstractmethod
from typing import Dict
from ontobdc.run.domain.machine.response import IntentScoreResponse


class IntentModelResolverPort(ABC):
    """
    Port for intent model resolution.
    """
    @property
    @abstractmethod
    def models(self) -> Dict[str, str]:
        """
        Returns the list of supported models.
        """
        ...

    @abstractmethod
    def parse_intent(self, text: str) -> IntentScoreResponse:
        """
        Parses the given text and returns an IntentScoreResponse.
        """
        ...
