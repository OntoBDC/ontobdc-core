#!/usr/bin/env python3

import sys
from datetime import datetime
from typing import Dict, List, Tuple


RESET: str = "\033[0m"
BOLD: str = "\033[1m"
GRAY: str = "\033[90m"
WHITE: str = "\033[37m"
RED: str = "\033[31m"
GREEN: str = "\033[32m"
YELLOW: str = "\033[33m"
BLUE: str = "\033[34m"
CYAN: str = "\033[36m"


def _get_level_style(level: str) -> Tuple[str, str, str]:
    normalized_level: str = level.upper()
    level_styles: Dict[str, Tuple[str, str, str]] = {
        "INFO": (BLUE, "▶", "INFO"),
        "WARN": (YELLOW, "⚠️ ", "WARNING"),
        "WARNING": (YELLOW, "⚠️ ", "WARNING"),
        "ERROR": (RED, "❌", "ERROR"),
        "DEBUG": (CYAN, "▶", "DEBUG"),
        "SUCCESS": (GREEN, "✔", "SUCCESS"),
        "NOTICE": (CYAN, "▶", "NOTICE"),
    }
    return level_styles.get(normalized_level, (WHITE, "•", normalized_level))


def _get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(level: str, message: str, *args: str) -> None:
    level_color: str
    level_icon: str
    normalized_level: str
    level_color, level_icon, normalized_level = _get_level_style(level)

    output_parts: List[str] = [
        f"{GRAY}[{_get_timestamp()}]{RESET} ",
        f"{level_color}{level_icon} {normalized_level}{RESET} ",
        f"{WHITE}{message}{RESET}",
    ]

    pair: str
    for pair in args:
        if "=" in pair:
            key: str
            value: str
            key, value = pair.split("=", 1)
            output_parts.append(f" {BLUE}{key}{RESET}={GRAY}{value}{RESET}")
            continue

        output_parts.append(f" {GRAY}{pair}{RESET}")

    sys.stdout.write("".join(output_parts) + "\n")


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        script_name: str = argv[0] if argv else "print_log.sh"
        sys.stdout.write(f"Usage: {script_name} <LEVEL> <MESSAGE> [KEY=VALUE ...]\n")
        return 1

    level: str = argv[1]
    message: str = argv[2]
    extra_args: List[str] = argv[3:]
    log(level, message, *extra_args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
