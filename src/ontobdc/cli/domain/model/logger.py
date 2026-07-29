from pydantic import BaseModel, ConfigDict
from ontobdc.cli.domain.port.logger import LogLevelPort, LogRepositoryPort, LogStrategyContainerPort


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


class LogStrategyConfig(BaseModel, LogStrategyContainerPort):
    """
    Configuration model for log strategies.
    Consolidates the legacy `shared.domain.resource.logger` container model.
    Repository implementations such as `NullLogRepository` live in adapters.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    log_level: LogLevelPort
    log_repository: LogRepositoryPort
