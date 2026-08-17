
from enum import Enum
from abc import ABC, abstractmethod
from typing import Callable, Optional


class LogLevelPort(str, Enum):
    """
    Port for log levels.
    """
    pass


class LogRepositoryPort(ABC):
    """
    Repository port for log resources.
    """
    @abstractmethod
    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        """
        Log a message to the repository.

        :param level: The severity level of the log.
        :param message: The log message to log.
        :param args: Optional contextual values appended to the same line.
        """
        pass


class LogStrategyContainerPort(ABC):
    """
    Port for objects that carry the dependencies required by a log strategy.
    """
    log_level: LogLevelPort
    log_repository: LogRepositoryPort


class LoggerAwarePort(ABC):
    """
    Port for classes that can receive a log strategy container.
    """
    @abstractmethod
    def set_log_strategy(self, log_strategy: "LogStrategyContainerPort") -> None:
        """
        Inject a log strategy container into the implementing class.
        """
        ...

    @property
    @abstractmethod
    def log_strategy(self) -> Optional[LogStrategyContainerPort]:
        """
        Returns the log strategy container.
        """
        ...
