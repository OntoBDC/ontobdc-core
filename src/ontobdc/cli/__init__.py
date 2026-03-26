
import os
import sys
from typing import Any, Dict, Optional
try:
    import yaml
except Exception:
    yaml = None
import argparse
import subprocess
from ontobdc.run.run import main as run_main

try:
    from ontobdc.list.list import main as list_main
except ImportError:
    list_main = None


def config_data() -> Optional[Dict[str, Any]]:
    current_dir: str = os.path.abspath(os.getcwd())
    while True:
        config_file: str = os.path.join(current_dir, ".__ontobdc__", "config.yaml")
        if os.path.isfile(config_file):
            try:
                with open(config_file, "r") as f:
                    if yaml is not None:
                        cfg = yaml.safe_load(f) or {}
                    else:
                        cfg = {}
                        for raw_line in f.read().splitlines():
                            line = raw_line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("engine:"):
                                cfg["engine"] = line.split("engine:", 1)[1].strip()
                    engine = cfg.get("engine", None)
                    if engine is None or engine not in ["venv", "docker", "colab"]:
                        return None

                    root_dir = cfg.get("directory", {}).get("root", {}).get("absolute_path", None)
                    if root_dir is None:
                        cfg.setdefault("directory", {}).setdefault("root", {})["absolute_path"] = current_dir

                    return cfg
            except Exception:
                return None

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            return None

        current_dir = parent_dir




    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to config.sh (src/ontobdc/config/config.sh)
    # cli/.. -> src/ontobdc -> config -> config.sh
    # config_script = os.path.join(current_dir, "..", "config", "config.sh")
    
    # if not os.path.exists(config_script):
    #     print(f"Error: config.sh not found at {config_script}")
    #     sys.exit(1)


def check_main(args):
    # Get the directory of this file (src/ontobdc/cli)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to check.sh (src/ontobdc/check/check.sh)
    # cli/.. -> src/ontobdc -> check -> check.sh
    check_script = os.path.join(current_dir, "..", "check", "check.sh")
    
    if not os.path.exists(check_script):
        print(f"Error: check.sh not found at {check_script}")
        sys.exit(1)
        
    # Build command arguments
    cmd = [check_script]
    if args.repair:
        cmd.append("--repair")
    
    # Execute the shell script
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing check script: {e}")
        sys.exit(1)


def dev_command(action, args, project_root: str):
    # Map dev commands to their scripts in src/ontobdc/dev
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # cli/.. -> src/ontobdc -> dev -> action.sh
    script_path = os.path.join(current_dir, "..", "dev", f"{action}.sh")
    
    if not os.path.exists(script_path):
        print(f"Error: {action}.sh not found at {script_path}")
        sys.exit(1)

    # We need to pass all arguments to the script
    # Since we are inside python, we need to reconstruct argv
    # But args here is from argparse.
    # The simplest way is to just pass sys.argv minus the first two elements (prog name and command)
    # However, for robustness let's just use the raw arguments
    
    cmd = [script_path] + sys.argv[2:]
    
    try:
        env = os.environ.copy()
        env["ONTOBDC_PROJECT_ROOT"] = project_root
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing {action} script: {e}")
        sys.exit(1)


def print_help():
    # Colors
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    WHITE = '\033[37m'
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    msg_box_script = os.path.join(current_dir, "message_box.sh")

    help_content = f"""
  {WHITE}Usage:{RESET}
    {GRAY}ontobdc{RESET} {CYAN}<command>{RESET} {GRAY}[flags/parameters]{RESET}

  {WHITE}Commands:{RESET}
    {CYAN}init{RESET}      {GRAY}Initialize ontobdc config with engine (venv|colab){RESET}
    {CYAN}check{RESET}     {GRAY}Run infrastructure checks{RESET}
    {CYAN}run{RESET}       {GRAY}Run a capability via ontobdc/run{RESET}
    {CYAN}list{RESET}      {GRAY}List all available capabilities{RESET}
    {CYAN}dev{RESET}       {GRAY}Developer tools (e.g., ontobdc dev commit){RESET}
"""

    if os.path.exists(msg_box_script):
         subprocess.run(["bash", msg_box_script, "GRAY", "OntoBDC", "CLI Help", help_content], check=False)
    else:
        print("")
        print(f"{WHITE}OntoBDC CLI{RESET}")
        print(help_content)
        print("")


def main():
    # If no args, print help
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1]
    
    if cmd in ["-h", "--help", "help"]:
        print_help()
        sys.exit(0)

    if cmd in ["-v", "--version", "version"]:
        try:
            from importlib.metadata import version
            ver = version("ontobdc")
        except Exception:
            ver = "unknown"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        msg_box_script = os.path.join(current_dir, "message_box.sh")
        
        if os.path.exists(msg_box_script):
             subprocess.run(["bash", msg_box_script, "BLUE", "OntoBDC", f"Version: {ver}", "Ontology-Based Data Capabilities"], check=False)
        else:
             print(f"OntoBDC Version: {ver}")
        sys.exit(0)
    
    if cmd == "init":
        from ontobdc.cli.init import init_main
        init_main()
        sys.exit(0)

    else:
        # Check if engine is installed/initialized
        current_dir = os.path.dirname(os.path.abspath(__file__))
        msg_box_script = os.path.join(current_dir, "message_box.sh")

        cfg = config_data()

        if not cfg:
            if os.path.exists(msg_box_script):
                msg = "OntoBDC is not initialized.\n\nPlease run \033[1;37montobdc init\033[0;90m to setup the project configuration."
                subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Initialized", msg], check=False)
            else:
                print("Error: OntoBDC is not initialized. Run 'ontobdc init'.")
            sys.exit(1)

        project_root: str = cfg.get("directory").get("root").get("absolute_path")
        if not project_root:
            project_root = os.getcwd()

        # is_engine_installed_script = os.path.join(current_dir, "..", "check", "infra", "is_engine_installed", "init.sh")

        # probe = os.getcwd()
        # for _ in range(12):
        #     if os.path.exists(os.path.join(probe, ".__ontobdc__", "config.yaml")):
        #         project_root = probe
        #         break
        #     parent = os.path.dirname(probe)
        #     if parent == probe:
        #         break
        #     probe = parent

        # if not project_root:
        #     if os.path.exists(msg_box_script):
        #         msg = "OntoBDC is not initialized.\n\nPlease run \033[1;37montobdc init\033[0;90m to setup the project configuration."
        #         subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Initialized", msg], check=False)
        #     else:
        #         print("Error: OntoBDC is not initialized. Run 'ontobdc init'.")
        #     sys.exit(1)

        # if os.path.exists(is_engine_installed_script):
        #     # We need to source the script and run the check function.
        #     # Since subprocess.run creates a new shell, we can just run a small bash snippet
        #     check_cmd = f"source {is_engine_installed_script} && check"
        #     try:
        #         subprocess.run(
        #             check_cmd,
        #             shell=True,
        #             check=True,
        #             executable="/bin/bash",
        #             stdout=subprocess.DEVNULL,
        #             stderr=subprocess.DEVNULL,
        #             cwd=project_root,
        #         )
        #     except subprocess.CalledProcessError:
        #         # Check failed (exit code != 0)
        #         if os.path.exists(msg_box_script):
        #              msg = "OntoBDC is not initialized.\n\nPlease run \033[1;37montobdc init\033[0;90m to setup the project configuration."
        #              subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Initialized", msg], check=False)
        #         else:
        #              print("Error: OntoBDC is not initialized. Run 'ontobdc init'.")
        #         sys.exit(1)
        
    if cmd == "run":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        run_main()
        
    elif cmd == "list":
        if list_main:
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            list_main()
        else:
            print("Error: 'list' module not found.")
            sys.exit(1)

    elif cmd == "check":
        parser = argparse.ArgumentParser(description="System Check")
        parser.add_argument("--repair", action="store_true", help="Attempt to repair issues")
        # Parse only arguments after 'check'
        args, unknown = parser.parse_known_args(sys.argv[2:])
        check_main(args)

    # elif cmd == "plan":
    #     current_dir = os.path.dirname(os.path.abspath(__file__))
    #     msg_box_script = os.path.join(current_dir, "message_box.sh")
        
    #     if os.path.exists(msg_box_script):
    #          subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Implemented Yet", "The 'plan' command is currently under development."], check=False)
    #     else:
    #          print("Error: Not Implemented Yet (message_box.sh not found)")
    #     sys.exit(1)

    elif cmd == "dev":
        dev_command("dev", None, project_root)

    else:
        print_log_script = os.path.join(current_dir, "print_log.sh")
        print("")
        subprocess.run(["bash", print_log_script, "ERROR", f"The '{cmd}' command was not found."], check=False)
        print("")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
