from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class SystemInstallProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the installation of a system.
    """


class SystemInstallStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> SystemInstallProcessStatePort:
        """
        Return the state the installation has reached.
        """
        ...


class SystemInstallStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> SystemInstallProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: SystemInstallProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: SystemInstallProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: SystemInstallProcessStatePort,
        to_state: SystemInstallProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the installation flow.
        """
        ...
