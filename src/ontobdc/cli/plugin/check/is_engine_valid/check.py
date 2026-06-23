
import sys
from . import VALID_ENGINES
from ontobdc.cli import ConfigDataAdapter


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Engine Valid", message)
        else:
            print(message, file=sys.stderr)

    try:
        cfg = ConfigDataAdapter().all

        engine = cfg.get("engine")
        if not engine:
            _print_error_log("engine is not set in config.yaml.", print_log)
            return 1

        
        if engine not in VALID_ENGINES:
            _print_error_log(f"Invalid engine '{engine}'. Valid options are: {', '.join(VALID_ENGINES)}", print_log)
            return 1

        return 0
    except Exception as e:
        _print_error_log(f"Error checking engine: {str(e)}", print_log)
        return 1

if __name__ == "__main__":
    sys.exit(main())
