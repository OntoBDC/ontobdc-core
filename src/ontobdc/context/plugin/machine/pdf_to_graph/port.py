from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class PdfToGraphProcessStatePort(str, Enum):
    """
    Base enum contract for PDF-to-knowledge-graph process states.
    """


class PdfToGraphStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> PdfToGraphProcessStatePort:
        """
        Read the PDF-to-graph context and return the state already reached.
        """
        ...


class PdfToGraphStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> PdfToGraphProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> PdfToGraphProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(
        self,
        to_state: PdfToGraphProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(
        self,
        to_state: PdfToGraphProcessStatePort,
    ) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: PdfToGraphProcessStatePort,
        to_state: PdfToGraphProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the PDF-to-knowledge-graph flow.
        """
        ...
