
from typing import Callable
from dataclasses import dataclass
from ontobdc.shared.domain.port.logger import LogLevelPort, LogRepositoryPort, LogStrategyContainerPort


class NullLogRepository(LogRepositoryPort):
    """
    Null-object repository for contexts where log persistence is optional.
    """
    def log(self, level: LogLevelPort, message: str) -> None:
        pass


@dataclass
class LogStrategyResource(LogStrategyContainerPort):
    """
    Resource for log strategies.
    """
    print_log: Callable[..., None]
    log_level: LogLevelPort
    log_repository: LogRepositoryPort


class LogLevel(LogLevelPort):
    """
    Enum representing log levels according to RFC 5424 (Syslog Protocol).
    """
    EMERGENCY = "EMERGENCY"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    INFORMATIONAL = "INFO"
    DEBUG = "DEBUG"
