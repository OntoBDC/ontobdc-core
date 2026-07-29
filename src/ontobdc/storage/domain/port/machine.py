
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import List, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse


class ContainerCreateProcessStatePort(str, Enum):
    """
    Base enum contract for storage container creation states.
    """


class ContainerCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
        target_path: Path,
    ) -> ContainerCreateProcessStatePort:
        ...

    @property
    @abstractmethod
    def process_state_class(self) -> Type[ContainerCreateProcessStatePort]:
        ...


class ContainerCreateStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def context(self) -> CliContextPort:
        """
        Execution context used by the container creation flow.
        """
        ...

    @property
    @abstractmethod
    def target_path(self) -> Path:
        """
        Filesystem path where the container should be created.
        """
        ...

    @property
    @abstractmethod
    def current_state(self) -> ContainerCreateProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[ContainerCreateProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: ContainerCreateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: ContainerCreateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: ContainerCreateProcessStatePort,
        to_state: ContainerCreateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the container creation flow.
        """
        ...


class DatasetCreateProcessStatePort(str, Enum):
    """
    Base enum contract for storage dataset creation states.
    """


class DatasetCreateStateEvaluatorPort(ABC):
    @abstractmethod
    def evaluate(
        self,
        context: CliContextPort,
    ) -> DatasetCreateProcessStatePort:
        ...

    @property
    @abstractmethod
    def process_state_class(self) -> Type[DatasetCreateProcessStatePort]:
        ...


class DatasetCreateStateTransitionHandlerPort(ABC):
    @property
    @abstractmethod
    def context(self) -> CliContextPort:
        """
        Execution context used by the dataset creation flow.
        """
        ...

    @property
    @abstractmethod
    def target_path(self) -> Path:
        """
        Filesystem path where the dataset should be created.
        """
        ...

    @property
    @abstractmethod
    def current_state(self) -> DatasetCreateProcessStatePort:
        ...

    @property
    @abstractmethod
    def state_sequence(self) -> List[DatasetCreateProcessStatePort]:
        ...

    @abstractmethod
    def can_transit_to(self, to_state: DatasetCreateProcessStatePort) -> bool:
        ...

    @abstractmethod
    def perform_state_transition(self, to_state: DatasetCreateProcessStatePort) -> None:
        ...

    @abstractmethod
    def validate_state_transition(
        self,
        from_state: DatasetCreateProcessStatePort,
        to_state: DatasetCreateProcessStatePort,
    ) -> bool:
        ...

    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Execute the dataset creation flow.
        """
        ...
