from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort


class ChainResponsibilityPort(ABC):
    """
    Contract for capabilities that may participate in a chain.

    Concrete chains define their own responsibility port by extending this
    contract. Capabilities opt into that chain by implementing its concrete
    responsibility port in addition to their normal capability contract.
    """

    @abstractmethod
    def can_handle(
        self,
        context: CliContextPort,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Return whether this capability can handle the current responsibility.
        """
        ...
