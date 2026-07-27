
from abc import abstractmethod
import os
import subprocess
import sys
from typing import Callable
from ontobdc.cli.domain.model.logger import LogLevel
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.cli.domain.port.logger import LogLevelPort, LogRepositoryPort


class BaseLoggerAdapter:
    @abstractmethod
    def log(self, level: LogLevelPort, message: str, *args) -> None:
        ...

    def log_debug(self, message: str) -> None:
        self.log(LogLevel.DEBUG, message)

    def log_info(self, message: str) -> None:
        self.log(LogLevel.INFORMATIONAL, message)

    def log_warning(self, message: str) -> None:
        self.log(LogLevel.WARNING, message)

    def log_error(self, message: str) -> None:
        self.log(LogLevel.ERROR, message)

    def log_critical(self, message: str) -> None:
        self.log(LogLevel.CRITICAL, message)

    def log_emergency(self, message: str) -> None:
        self.log(LogLevel.EMERGENCY, message)

    def log_alert(self, message: str) -> None:
        self.log(LogLevel.ALERT, message)

    def log_notice(self, message: str) -> None:
        self.log(LogLevel.NOTICE, message)

    @staticmethod
    def log_wrapper(log_instance: 'BaseLoggerAdapter') -> Callable[..., None]:
        return log_instance.log


class NullLogRepository(LogRepositoryPort, BaseLoggerAdapter):
    """
    Null-object repository for contexts where log persistence is optional.
    """
    def log(self, level: LogLevelPort, message: str, *args) -> None:
        pass


class StandardConsoleLogger(LogRepositoryPort, BaseLoggerAdapter):
    """
    Logger that prints log messages to the console.
    """
    def log(self, level: LogLevelPort, message: str, *args) -> None:
        print(f"[{level.value}] {message} {' '.join(args)}")


class InLineLogger(LogRepositoryPort, BaseLoggerAdapter):
    """
    Logger that prints log messages to the console in-line.
    """
    def log(self, level: LogLevelPort, message: str, *args) -> None:
        """Wrapper to call print_log.sh"""
        try:
            current_dir = ConfigDataAdapter().script_dir / "cli" / "adapter"
            log_script = os.path.join(current_dir, "print_log.sh")

            if os.path.exists(log_script):
                level_value: str = str(getattr(level, "value", level))
                cmd = [sys.executable, log_script, level_value, message] + [str(arg) for arg in args]
                subprocess.run(cmd, check=False)
                return

        except Exception as e:
            print(f"Error logging message: {e}")

        # Fallback
        StandardConsoleLogger().log(level, message, *args)


