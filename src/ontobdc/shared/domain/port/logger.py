
from enum import Enum
from typing import Callable, Optional
from abc import ABC, abstractmethod


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
    def log(self, level: LogLevelPort, message: str) -> None:
        """
        Log a message to the repository.

        :param level: The severity level of the log.
        :param message: The log message to log.
        """
        pass


class LogStrategyContainerPort(ABC):
    """
    Port for objects that carry the dependencies required by a log strategy.
    """
    print_log: Callable[..., None]
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

    def _print_log(self, level: LogLevelPort, message: str, title: str = None, *args: str) -> None:
        if self.log_strategy is None:
            return

        self.log_strategy.print_log(level.value, title or "", message, *args)

        if self.log_repository is None:
            return

        self.repository.log(level, message)

