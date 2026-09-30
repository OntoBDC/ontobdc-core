from abc import abstractmethod
import sys
from typing import ClassVar, Dict, List, TextIO, Tuple, Callable, Optional
from datetime import datetime

from ontobdc.cli.domain.port.logger import LogLevelPort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogLevel, LogLevelPolicy
from ontobdc.shared.adapter.terminal_color import TerminalColor


class InlineLogFormatter:
    """
    Formats a single in-line log entry as one colored terminal line.
    """
    _LEVEL_STYLES: ClassVar[Dict[str, Tuple[str, str]]] = {
        "INFO": (TerminalColor.BLUE, "\u25b6"),
        "WARN": (TerminalColor.YELLOW, "\u26a0\ufe0f "),
        "WARNING": (TerminalColor.YELLOW, "\u26a0\ufe0f "),
        "ERROR": (TerminalColor.RED, "\u274c"),
        "DEBUG": (TerminalColor.CYAN, "\u25b6"),
        "SUCCESS": (TerminalColor.GREEN, "\u2714"),
        "NOTICE": (TerminalColor.CYAN, "\u25b6"),
    }
    _LEVEL_ALIASES: ClassVar[Dict[str, str]] = {"WARN": "WARNING"}
    _DEFAULT_STYLE: ClassVar[Tuple[str, str]] = (TerminalColor.WHITE, "\u2022")
    _TIMESTAMP_FORMAT: ClassVar[str] = "%H:%M:%S"

    def format(
        self,
        level: str,
        message: str,
        args: List[str],
        *,
        timestamp: datetime,
    ) -> str:
        normalized_level: str = level.upper()
        level_color, level_icon = self._LEVEL_STYLES.get(
            normalized_level,
            self._DEFAULT_STYLE,
        )
        display_level: str = self._LEVEL_ALIASES.get(
            normalized_level,
            normalized_level,
        )
        parts: List[str] = [
            f"{TerminalColor.GRAY}[{timestamp:{self._TIMESTAMP_FORMAT}}]"
            f"{TerminalColor.RESET} ",
            f"{level_color}{level_icon} {display_level}{TerminalColor.RESET} ",
            f"{TerminalColor.WHITE}{message}{TerminalColor.RESET}",
        ]
        parts.extend(self._argument_part(argument) for argument in args)

        return "".join(parts)

    def _argument_part(self, argument: str) -> str:
        key, separator, value = argument.partition("=")
        if not separator:
            return f" {TerminalColor.GRAY}{argument}{TerminalColor.RESET}"

        return (
            f" {TerminalColor.BLUE}{key}{TerminalColor.RESET}"
            f"={TerminalColor.GRAY}{value}{TerminalColor.RESET}"
        )


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
        formatter: Optional[InlineLogFormatter] = None,
    ) -> None:
        super().__init__(log_level=log_level)
        self._stream: TextIO = stream if stream is not None else sys.stdout
        self._clock: Callable[[], datetime] = clock or datetime.now
        self._formatter: InlineLogFormatter = formatter or InlineLogFormatter()

    def log(
        self,
        level: LogLevelPort,
        message: str,
        *args: object,
    ) -> None:
        if not self._should_log(level):
            return
        level_value: str = str(getattr(level, "value", level))
        line: str = self._formatter.format(
            level_value,
            message,
            [str(argument) for argument in args],
            timestamp=self._clock(),
        )
        self._stream.write(line + "\n")
        self._stream.flush()
