from typing import List, Optional, Tuple

from ontobdc.cli.domain.model.logger import LogLevel, LogStrategyConfig
from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


class LogLevelStrategy(ParameterPort, CliContextStrategyPort, LoggerAwarePort):
    """Inject one process-local log threshold from the global CLI arguments."""

    METADATA = ParameterMetadata(
        id="org.ontobdc.domain.cli.parameter.log-level",
        version="0.17.0",
        name="log_level",
        description="Resolve the log threshold for the current CLI execution.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=LogLevel,
    )

    def __init__(self) -> None:
        self._log_strategy: Optional[LogStrategyConfig] = None
        self._remaining_args: List[str] = []

    @property
    def log_strategy(self) -> Optional[LogStrategyConfig]:
        return self._log_strategy

    @property
    def remaining_args(self) -> List[str]:
        return list(self._remaining_args)

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy

    def execute(self, context: CliContextPort) -> CliContextPort:
        existing_value: Any = context.get_parameter_value("log_level")
        if existing_value is not None:
            if isinstance(existing_value, LogLevel):
                resolved_level = existing_value
            else:
                raw_existing: str = str(existing_value).strip()
                if not raw_existing:
                    return context
                resolved_level = self._resolve(raw_existing)
            if self._log_strategy is not None:
                self._log_strategy = LogStrategyConfig(
                    log_level=resolved_level,
                    log_repository=self._log_strategy.log_repository,
                )
            self._remaining_args = list(context.raw_args)
            context.set_parameter_value("log_level", resolved_level)
            return context

        raw_level, remaining_args = self._consume(list(context.raw_args))
        self._remaining_args = remaining_args
        if raw_level is None:
            return context

        if self._log_strategy is None:
            raise RuntimeError("LogLevelStrategy requires an injected log strategy.")

        resolved_implicit_level = self._resolve(raw_level)
        self._log_strategy = LogStrategyConfig(
            log_level=resolved_implicit_level,
            log_repository=self._log_strategy.log_repository,
        )
        context.set_parameter_value("log_level", resolved_implicit_level)
        return context

    @classmethod
    def _consume(cls, args: List[str]) -> Tuple[Optional[str], List[str]]:
        raw_level: Optional[str] = None
        remaining_args: List[str] = []
        index = 0

        while index < len(args):
            argument = args[index]
            if argument == "--log-level":
                if raw_level is not None:
                    raise ValueError("--log-level may be provided only once.")
                if index + 1 >= len(args) or args[index + 1].startswith("-"):
                    raise ValueError("--log-level requires a level value.")
                raw_level = args[index + 1]
                index += 2
                continue

            if argument.startswith("--log-level="):
                if raw_level is not None:
                    raise ValueError("--log-level may be provided only once.")
                raw_level = argument.split("=", 1)[1]
                if not raw_level.strip():
                    raise ValueError("--log-level requires a level value.")
                index += 1
                continue

            remaining_args.append(argument)
            index += 1

        return raw_level, remaining_args

    @staticmethod
    def _resolve(raw_level: str) -> LogLevel:
        normalized = raw_level.strip().upper().replace("-", "_")
        aliases = {
            "WARN": LogLevel.WARNING,
            "INFORMATIONAL": LogLevel.INFORMATIONAL,
        }
        if normalized in aliases:
            return aliases[normalized]

        for level in LogLevel:
            if normalized in {level.name, level.value}:
                return level

        supported = ", ".join(level.value for level in LogLevel)
        raise ValueError(
            f"Unsupported log level: {raw_level!r}. "
            f"Supported levels: {supported}."
        )
