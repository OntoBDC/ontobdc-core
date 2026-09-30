from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict, Optional
from dataclasses import dataclass

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.port.chain import ChainResponsibilityPort


@dataclass(frozen=True)
class FileOpenResult:
    """
    Outcome of running the open-file chain for one file.

    ``handled`` declares whether a chain member claimed the request.
    When ``True`` the chain considers the work done and reports that
    member's result to the caller; ``error`` then tells a claimed but
    failed attempt apart from a successful one.
    """

    handled: bool = False
    handler: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


class OpenFileRequestPort:
    """Canonical context keys consumed by the open-file machine."""

    PATH_KEY: ClassVar[str] = "file_open_path"
    KIND_KEY: ClassVar[str] = "file_open_kind"
    NAME_KEY: ClassVar[str] = "file_open_name"
    DATA_KEY: ClassVar[str] = "file_open_data"
    LANGUAGE_KEY: ClassVar[str] = "file_open_language"
    MIME_KEY: ClassVar[str] = "file_open_mime"
    CAPABILITY_BY_MIME_KEY: ClassVar[str] = "open_file_capability"


class OpenFileProcessStatePort(str, Enum):
    """Base enum contract for open-file process states."""


class OpenFileStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(self, context: CliContextPort) -> OpenFileProcessStatePort:
        """Read persisted open-file state for the current request target."""
        ...


class OpenFileStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def current_state(self) -> OpenFileProcessStatePort:
        ...

    @property
    @abstractmethod
    def observed_state(self) -> OpenFileProcessStatePort:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: OpenFileProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: OpenFileProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: OpenFileProcessStatePort,
        to_state: OpenFileProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> Dict[str, Dict[str, Any]]:
        """Execute the open-file state machine and return the opening results."""
        ...


class OpenFileChainSupport(OpenFileRequestPort, ChainResponsibilityPort):
    """Responsibility contract for the open-file strategy chain."""
