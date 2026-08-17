from typing import Any, ClassVar, Dict

from pydantic import BaseModel, ConfigDict
from ontobdc.cli.domain.port.logger import LogLevelPort, LogRepositoryPort, LogStrategyContainerPort


class LogLevel(LogLevelPort):
    """
    Enum representing RFC 5424 log levels plus the internal SUCCESS level.

    SUCCESS remains a distinct internal level and is severity-equivalent to
    NOTICE for threshold filtering.
    """
    EMERGENCY = "EMERGENCY"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    NOTICE = "NOTICE"
    SUCCESS = "SUCCESS"
    INFORMATIONAL = "INFO"
    DEBUG = "DEBUG"


class LogLevelPolicy:
    """Central policy for log-level defaults, ordering, and filtering."""

    DEFAULT: ClassVar[LogLevel] = LogLevel.NOTICE
    _PRIORITY: ClassVar[Dict[str, int]] = {
        "EMERGENCY": 0,
        "ALERT": 1,
        "CRITICAL": 2,
        "ERROR": 3,
        "WARNING": 4,
        "WARN": 4,
        "NOTICE": 5,
        "SUCCESS": 5,
        "INFO": 6,
        "DEBUG": 7,
    }

    @classmethod
    def priority(cls, level: LogLevelPort) -> int:
        level_value: str = str(getattr(level, "value", level)).strip().upper()
        try:
            return cls._PRIORITY[level_value]
        except KeyError as exception:
            raise ValueError(
                f"Unsupported log level: {level_value!r}"
            ) from exception

    @classmethod
    def should_log(
        cls,
        event_level: LogLevelPort,
        threshold: LogLevelPort,
    ) -> bool:
        return cls.priority(event_level) <= cls.priority(threshold)


class LogStrategyConfig(BaseModel, LogStrategyContainerPort):
    """
    Configuration model for log strategies.
    Consolidates the legacy `shared.domain.resource.logger` container model.
    Repository implementations such as `NullLogRepository` live in adapters.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    log_level: LogLevelPort = LogLevelPolicy.DEFAULT
    log_repository: LogRepositoryPort

    def model_post_init(self, __context: Any) -> None:
        set_log_level = getattr(self.log_repository, "set_log_level", None)
        if callable(set_log_level):
            set_log_level(self.log_level)
