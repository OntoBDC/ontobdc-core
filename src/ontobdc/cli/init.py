import os
import sys
import argparse
import json
import yaml
import subprocess

def log(level, message, *args):
    """Wrapper to call print_log.sh"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_script = os.path.join(current_dir, "print_log.sh")
    
    if os.path.exists(log_script):
        cmd = ["bash", log_script, level, message] + list(args)
        subprocess.run(cmd, check=False)
    else:
        # Fallback
        print(f"[{level}] {message} {' '.join(args)}")

def message_box(color, title_type, title_text, message):
    """Wrapper to call message_box.sh"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    msg_box_script = os.path.join(current_dir, "message_box.sh")

    if os.path.exists(msg_box_script):
        subprocess.run(["bash", msg_box_script, color, title_type, title_text, message], check=False)
    else:
        # Fallback
        print(f"[{title_type}] {message}")

def _confirm_context_creation(path: str) -> bool:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    msg_box_script = os.path.join(current_dir, "message_box.sh")
    if os.path.exists(msg_box_script):
        subprocess.run(
            [
                "bash",
                msg_box_script,
                "GRAY",
                "OntoBDC",
                "Init Context",
                f"Confirm context creation in this directory?\n\nPath:\n{path}",
            ],
            check=False,
        )
    else:
        print(f"Confirm context creation in this directory?\n\nPath:\n{path}\n")

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        try:
            answer = input("Confirm? [y/N]: ").strip().lower()
        except EOFError:
            return False
        return answer in {"y", "yes"}

    import termios
    import tty

    cyan = "\033[36m"
    gray = "\033[90m"
    white = "\033[37m"
    reset = "\033[0m"

    options = ["Yes", "No"]
    selected = 0

    def render() -> None:
        sys.stdout.write("\033[2K\r")
        pointer = f"{cyan}➜{reset}"
        line1 = f"  {pointer} {white}{options[0]}{reset}" if selected == 0 else f"    {gray}{options[0]}{reset}"
        sys.stdout.write(line1 + "\n")
        sys.stdout.write("\033[2K\r")
        line2 = f"  {pointer} {white}{options[1]}{reset}" if selected == 1 else f"    {gray}{options[1]}{reset}"
        sys.stdout.write(line2 + "\n")
        sys.stdout.write("\033[2K\r")
        sys.stdout.write(f"  {gray}Use ↑/↓ and Enter (Esc cancels){reset}\n")
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\n")
        render()
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\n", "\r"):
                return selected == 0
            if ch in ("y", "Y"):
                return True
            if ch in ("n", "N"):
                return False
            if ch == "\x1b":
                if sys.stdin.read(1) == "[":
                    code = sys.stdin.read(1)
                    if code == "A":
                        selected = (selected - 1) % 2
                    elif code == "B":
                        selected = (selected + 1) % 2
                    else:
                        return False
                else:
                    return False

                sys.stdout.write("\033[3A")
                render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def init_context_main() -> None:
    parser = argparse.ArgumentParser(description="Initialize OntoBDC context (RO-Crate)")
    args, unknown = parser.parse_known_args(sys.argv[3:])

    cwd = os.getcwd()
    confirmed = _confirm_context_creation(cwd)
    if not confirmed:
        log("INFO", "Context creation cancelled.", f"path={cwd}")
        return

    try:
        from ontobdc.module.resource.adapter.folder import LocalFolderAdapter
        from ontobdc.module.resource.adapter.repository import LocalObjectDatasetRepository
        from ontobdc.module.resource.adapter.crate import RoCrateDatasetAdapter
    except Exception:
        message_box(
            "RED",
            "Error",
            "Dependencies Missing",
            "Could not import RO-Crate dependencies.\n\nRun:\n  ontobdc check --repair",
        )
        sys.exit(1)

    folder = LocalFolderAdapter(path=cwd)
    repo = LocalObjectDatasetRepository(folder, ensure_path=True)

    try:
        adapter = RoCrateDatasetAdapter(repo)
        adapter.create_ro_crate(output_dir=cwd)
    except Exception as e:
        message_box("RED", "Error", "Init Context Failed", str(e))
        sys.exit(1)

    message_box(
        "GREEN",
        "Success",
        "Context Created",
        f"RO-Crate created at:\n\n{os.path.join(cwd, '.__ontobdc__', 'ro-crate-metadata.json')}",
    )


def init_engine_main():
    """
    Initialize OntoBDC configuration.
    Creates .__ontobdc__ directory and config.yaml with specified engine.
    """
    parser = argparse.ArgumentParser(description="Initialize OntoBDC configuration")
    parser.add_argument("engine", nargs="?", help="Execution engine (e.g. venv, colab). If omitted, attempts auto-detection.")
    
    # We only parse arguments relevant to init
    args, unknown = parser.parse_known_args(sys.argv[2:])
    
    engine = args.engine

    # DRY: Automatic engine detection if not provided
    if not engine:
        # Check for Colab
        if os.path.exists("/content"):
            engine = "colab"
        # Check for Venv
        elif sys.prefix != sys.base_prefix:
            engine = "venv"
        else:
            log("ERROR", "Engine not specified and could not be automatically detected (not in Colab or active Venv).")
            print("Please specify engine: ontobdc init <engine>")
            sys.exit(1)

        print("")
        log("INFO", f"Automatically detected engine: {engine}")

    # 1. Validate Engine against check/config.json
    # Locate config.json relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # cli/.. -> src/ontobdc -> check -> config.json
    config_json_path = os.path.join(current_dir, "..", "check", "config.json")
    
    valid_engines = []
    if os.path.exists(config_json_path):
        try:
            with open(config_json_path, 'r') as f:
                data = json.load(f)
                valid_engines = data.get('config', {}).get('engines', [])
        except Exception as e:
            log("WARN", f"Failed to load config.json validation: {e}")
    
    if valid_engines and engine not in valid_engines:
        log("ERROR", f"Invalid engine '{engine}'.")
        print(f"Valid engines are: {', '.join(valid_engines)}")
        sys.exit(1)

    # 2. Create .__ontobdc__ directory in current working directory
    cwd = os.getcwd()
    ontobdc_dir = os.path.join(cwd, ".__ontobdc__")
    config_file = os.path.join(ontobdc_dir, "config.yaml")

    if os.path.exists(config_file):
        message_box("YELLOW", "Warning", "Already Initialized", "OntoBDC is already initialized in this directory.")
        return

    if not os.path.exists(ontobdc_dir):
        log("INFO", f"Creating directory {ontobdc_dir}...")
        os.makedirs(ontobdc_dir)
    else:
        log("DEBUG", f"Directory {ontobdc_dir} already exists.")

    # 3. Create/Update config.yaml
    config_data = {}
    if os.path.exists(config_file):
        log("INFO", f"Updating existing config at {config_file}...")
        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        except Exception:
            pass
    else:
        log("INFO", f"Creating new config file at {config_file}...")

    # Set engine
    config_data['engine'] = engine
    
    try:
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        log("SUCCESS", f"Engine set to '{engine}'", f"path={config_file}")
    except Exception as e:
        log("ERROR", f"Error writing config file: {e}")
        sys.exit(1)

    # 4. Run Check Repair (optional but recommended in setup.sh logic)
    # We delegate to check command
    print("")
    from ontobdc.cli import check_main
    
    # Mock args for check
    class CheckArgs:
        repair = True
        
    try:
        check_main(CheckArgs())
    except SystemExit:
        # check_main calls sys.exit, we catch it to not crash if check fails but init succeeded
        pass


def init_main():
    if len(sys.argv) >= 3 and sys.argv[2] == "context":
        init_context_main()
        return
    init_engine_main()
