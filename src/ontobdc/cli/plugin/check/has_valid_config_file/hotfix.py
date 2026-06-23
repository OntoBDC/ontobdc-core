
import os
import sys
import yaml


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Valid Config File", message)
        else:
            print(message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Valid Config File", message)
        else:
            print(message, file=sys.stderr)

    try:
        root_dir: str = os.environ.get("ONTOBDC_PROJECT_ROOT", os.getcwd())

        config_dir: str = os.path.join(root_dir, ".__ontobdc__")
        config_file: str = os.path.join(config_dir, "config.yaml")

        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            _print_info_log(f"Created config directory at {config_dir}", print_log)

        if not os.path.exists(config_file):
            default_config = {
                "directory": {
                    "root": {
                        "absolute_path": root_dir
                    }
                }
            }
            with open(config_file, "w") as f:
                yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
            _print_info_log(f"Created default config file at {config_file}", print_log)
        else:
            try:
                with open(config_file, "r") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError:
                backup_file = config_file + ".bak"
                os.rename(config_file, backup_file)
                _print_info_log(f"Backed up invalid config file to {backup_file}", print_log)
                
                default_config = {
                    "directory": {
                        "root": {
                            "absolute_path": root_dir
                        }
                    }
                }
                with open(config_file, "w") as f:
                    yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
                _print_info_log(f"Created new default config file at {config_file}", print_log)
            
        return 0
    except Exception as e:
        _print_error_log(f"Error applying config file hotfix: {e}", print_log)
        return 1

if __name__ == "__main__":
    sys.exit(main())
