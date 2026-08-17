
from abc import abstractmethod
from datetime import datetime
import sys
from typing import Callable, Dict, List, Optional, TextIO, Tuple

from ontobdc.cli.domain.model.logger import (
    LogLevel,
    LogLevelPolicy,
)
from ontobdc.cli.domain.port.logger import LogLevelPort, LogRepositoryPort
from ontobdc.shared.adapter.terminal_color import (
    RESET as _RESET,
    GRAY as _GRAY,
    WHITE as _WHITE,
    RED as _RED,
    GREEN as _GREEN,
    YELLOW as _YELLOW,
    BLUE as _BLUE,
    CYAN as _CYAN,
)


def _get_level_style(level: str) -> Tuple[str, str, str]:
    normalized_level: str = level.upper()
    level_styles: Dict[str, Tuple[str, str, str]] = {
        "INFO": (_BLUE, "▶", "INFO"),
        "WARN": (_YELLOW, "⚠️ ", "WARNING"),
        "WARNING": (_YELLOW, "⚠️ ", "WARNING"),
        "ERROR": (_RED, "❌", "ERROR"),
        "DEBUG": (_CYAN, "▶", "DEBUG"),
        "SUCCESS": (_GREEN, "✔", "SUCCESS"),
        "NOTICE": (_CYAN, "▶", "NOTICE"),
    }
    return level_styles.get(
        normalized_level,
        (_WHITE, "•", normalized_level),
    )


def _format_inline_log(
    level: str,
    message: str,
    args: List[str],
    *,
    timestamp: datetime,
) -> str:
    level_color, level_icon, normalized_level = _get_level_style(level)
    output_parts: List[str] = [
        f"{_GRAY}[{timestamp:%H:%M:%S}]{_RESET} ",
        f"{level_color}{level_icon} {normalized_level}{_RESET} ",
        f"{_WHITE}{message}{_RESET}",
    ]

    for argument in args:
        if "=" in argument:
            key, value = argument.split("=", 1)
            output_parts.append(
                f" {_BLUE}{key}{_RESET}={_GRAY}{value}{_RESET}"
            )
            continue

        output_parts.append(f" {_GRAY}{argument}{_RESET}")

    return "".join(output_parts)


class BaseLoggerAdapter:
    def __init__(
        self,
        log_level: LogLevelPort = LogLevelPolicy.DEFAULT,
    ) -> None:
        self._log_level: LogLevelPort = log_level

    @property
    def log_level(self) -> LogLevelPort:
        return self._log_level

    def set_log_level(self, log_level: LogLevelPort) -> None:
        self._log_level = log_level

    def _should_log(self, level: LogLevelPort) -> bool:
        try:
            return LogLevelPolicy.should_log(level, self._log_level)
        except ValueError:
            return True

    @abstractmethod
    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        ...

    def log_debug(self, message: str, *args: object) -> None:
        self.log(LogLevel.DEBUG, message, *args)

    def log_info(self, message: str, *args: object) -> None:
        self.log(LogLevel.INFORMATIONAL, message, *args)

    def log_warning(self, message: str, *args: object) -> None:
        self.log(LogLevel.WARNING, message, *args)

    def log_error(self, message: str, *args: object) -> None:
        self.log(LogLevel.ERROR, message, *args)

    def log_critical(self, message: str, *args: object) -> None:
        self.log(LogLevel.CRITICAL, message, *args)

    def log_emergency(self, message: str, *args: object) -> None:
        self.log(LogLevel.EMERGENCY, message, *args)

    def log_alert(self, message: str, *args: object) -> None:
        self.log(LogLevel.ALERT, message, *args)

    def log_notice(self, message: str, *args: object) -> None:
        self.log(LogLevel.NOTICE, message, *args)

    def log_success(self, message: str, *args: object) -> None:
        self.log(LogLevel.SUCCESS, message, *args)

    @staticmethod
    def log_wrapper(log_instance: 'BaseLoggerAdapter') -> Callable[..., None]:
        return log_instance.log


class NullLogRepository(LogRepositoryPort, BaseLoggerAdapter):
    """
    Null-object repository for contexts where log persistence is optional.
    """
    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        pass


class StandardConsoleLogger(LogRepositoryPort, BaseLoggerAdapter):
    """
    Logger that prints log messages to the console.
    """
    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        if not self._should_log(level):
            return
        print(f"[{level.value}] {message} {' '.join(str(arg) for arg in args)}")


class InLineLogger(LogRepositoryPort, BaseLoggerAdapter):
    """
    Logger that prints log messages to the console in-line.
    """
    def __init__(
        self,
        stream: Optional[TextIO] = None,
        clock: Optional[Callable[[], datetime]] = None,
        log_level: LogLevelPort = LogLevelPolicy.DEFAULT,
    ) -> None:
        super().__init__(log_level=log_level)
        self._stream: TextIO = stream if stream is not None else sys.stdout
        self._clock: Callable[[], datetime] = clock or datetime.now

    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        if not self._should_log(level):
            return
        level_value: str = str(getattr(level, "value", level))
        line: str = _format_inline_log(
            level_value,
            message,
            [str(argument) for argument in args],
            timestamp=self._clock(),
        )
        self._stream.write(line + "\n")
        self._stream.flush()
