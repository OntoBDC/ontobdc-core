
import os
import sys
import yaml
from ontobdc.shared.adapter.config import ConfigDataAdapter


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Valid Config File", message)
        else:
            print(message, file=sys.stderr)

    try:
        try:
            root_dir = ConfigDataAdapter().root_dir
        except ValueError:
            _print_error_log("Project configuration file (.__ontobdc__/config.yaml) not found.", print_log)
            return 1

        config_file = os.path.join(root_dir, ".__ontobdc__", "config.yaml")

        if not os.path.exists(config_file):
            _print_error_log(f"Config file not found: {config_file}", print_log)
            return 1

        with open(config_file, "r") as f:
            yaml.safe_load(f)

        if not isinstance(ConfigDataAdapter().all, dict):
            _print_error_log(f"Config file is not a valid YAML dictionary: {config_file}", print_log)
            return 1

        return 0
    except yaml.YAMLError as e:
        _print_error_log(f"Invalid YAML in config file: {str(e)}", print_log)
        return 1
    except Exception as e:
        _print_error_log(f"Error checking config file: {str(e)}", print_log)
        return 1

if __name__ == "__main__":
    sys.exit(main())
