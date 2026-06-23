
import os
import sys
from pathlib import Path
from typing import Optional
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Root Dir", message)
        else:
            print(message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Root Dir", message)
        else:
            print(message, file=sys.stderr)

    config_adapter: ConfigDataPort = ConfigDataAdapter()

    # Use adapter to check if configuration is already valid
    try:
        root_dir: Path = config_adapter.root_dir
        config_file: Path = config_adapter.config_file

        if root_dir.exists() and root_dir.is_dir() and config_file.exists():
            _print_info_log("Project root is already correctly set.", print_log)
            return 0
    except Exception:
        # If adapter fails, continue with hotfix logic
        pass

    # Try to discover project root from current working directory
    discovered_root: Path = config_adapter.find_project_root(Path.cwd().resolve())

    if discovered_root and discovered_root.exists():
        os.environ["ONTOBDC_PROJECT_ROOT"] = str(discovered_root.resolve())
        _print_info_log(f"Project root dynamically set to: {discovered_root.resolve()}", print_log)
        return 0


if __name__ == "__main__":
    sys.exit(main())
