
import sys
from ontobdc.cli import ConfigDataAdapter


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Directory Root Set", message)
        else:
            print(message, file=sys.stderr)

    try:
        cfg = ConfigDataAdapter().all

        directory = cfg.get("directory")
        if not isinstance(directory, dict):
            _print_error_log("directory.root.absolute_path is not set in config.yaml.", print_log)
            return 1

        root = directory.get("root")
        if not isinstance(root, dict):
            _print_error_log("directory.root.absolute_path is not set in config.yaml.", print_log)
            return 1

        abs_path = root.get("absolute_path")
        if not abs_path:
            _print_error_log("directory.root.absolute_path is not set in config.yaml.", print_log)
            return 1

        return 0
    except Exception as e:
        _print_error_log(f"Error checking directory root: {str(e)}", print_log)
        return 1

if __name__ == "__main__":
    sys.exit(main())
