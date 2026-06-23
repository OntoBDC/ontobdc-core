
import os
import sys
import yaml
from . import VALID_ENGINES
from ontobdc.shared.adapter.config import ConfigDataAdapter


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Engine Valid", message)
        else:
            print(message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Engine Valid", message)
        else:
            print(message, file=sys.stderr)

    try:
        try:
            root_dir = ConfigDataAdapter().root_dir
        except ValueError:
            _print_error_log("Project configuration file (.__ontobdc__/config.yaml) not found. Run config file hotfix first.", print_log)
            return 1

        config_file = os.path.join(root_dir, ".__ontobdc__", "config.yaml")

        if not os.path.exists(config_file):
            _print_error_log(f"Config file not found: {config_file}", print_log)
            return 1

        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f) or {}

        engine = cfg.get("engine")

        if engine not in VALID_ENGINES:
            cfg["engine"] = "venv"
            with open(config_file, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
            _print_info_log(f"Updated engine to 'venv' in {config_file}", print_log)

        return 0
    except Exception as e:
        _print_error_log(f"Error applying engine hotfix: {e}", print_log)
        return 1

if __name__ == "__main__":
    sys.exit(main())
