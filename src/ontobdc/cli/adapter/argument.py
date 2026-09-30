import sys
from typing import Dict, List, Tuple, Optional

from ontobdc.cli.domain.model.logger import LogLevel, LogLevelPolicy


class CliGlobalArgumentParserAdapter:
    _OUTPUT_FLAGS: Tuple[str, ...] = (
        "--json",
        "--rich",
        "--html",
        "--silent",
        "-s",
    )

    def strip_output_flags(
        self,
        argv: Optional[List[str]] = None,
    ) -> List[str]:
        source: List[str] = list(sys.argv[1:] if argv is None else argv)
        return [argument for argument in source if argument not in self._OUTPUT_FLAGS]

    def consume_log_level(
        self,
        arguments: List[str],
    ) -> Tuple[Optional[LogLevel], List[str]]:
        raw_level: Optional[str]
        remaining_arguments: List[str]
        raw_level, remaining_arguments = self._consume(arguments)
        if raw_level is None:
            return None, remaining_arguments
        return self._resolve(raw_level), remaining_arguments

    @staticmethod
    def _consume(arguments: List[str]) -> Tuple[Optional[str], List[str]]:
        raw_level: Optional[str] = None
        remaining_arguments: List[str] = []
        index: int = 0

        while index < len(arguments):
            argument: str = arguments[index]
            if argument == "--log-level":
                if raw_level is not None:
                    raise ValueError("--log-level may be provided only once.")
                if (
                    index + 1 >= len(arguments)
                    or arguments[index + 1].startswith("-")
                ):
                    raise ValueError("--log-level requires a level value.")
                raw_level = arguments[index + 1]
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

            remaining_arguments.append(argument)
            index += 1

        return raw_level, remaining_arguments

    @staticmethod
    def _resolve(raw_level: str) -> LogLevel:
        normalized_level: str = raw_level.strip().upper().replace("-", "_")
        aliases: Dict[str, LogLevel] = {
            "RESET": LogLevelPolicy.DEFAULT,
            "WARN": LogLevel.WARNING,
            "INFORMATIONAL": LogLevel.INFORMATIONAL,
        }
        if normalized_level in aliases:
            return aliases[normalized_level]

        level: LogLevel
        for level in LogLevel:
            if normalized_level in {level.name, level.value}:
                return level

        supported_levels: List[str] = [level.value for level in LogLevel]
        supported: str = ", ".join([*supported_levels, "RESET"])
        raise ValueError(
            f"Unsupported log level: {raw_level!r}. "
            f"Supported levels: {supported}."
        )
