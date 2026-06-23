
import os
from pathlib import Path
import sys
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Root Dir", message)
        else:
            print(message, file=sys.stderr)

    config_adapter: ConfigDataPort = ConfigDataAdapter()
    root_dir: Path = config_adapter.root_dir

    if root_dir.exists() and root_dir.is_dir():
        config_file = config_adapter.config_file
        if config_file.exists():
            return 0

    _print_error_log("Project root directory is not properly set or configuration is missing.", print_log)
    return 1

if __name__ == "__main__":
    sys.exit(main())
