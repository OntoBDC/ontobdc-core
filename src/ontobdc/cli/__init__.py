
import os
import sys
from typing import Any, Dict, Optional
import yaml
import argparse
import subprocess
from ontobdc.run.run import main as run_main

try:
    from ontobdc.list.list import main as list_main
except ImportError:
    list_main = None


def get_root_dir() -> Optional[str]:
    """
    Find the root directory of the project by looking for the .__ontobdc__ directory.
    """
    env_root = os.environ.get("ONTOBDC_PROJECT_ROOT")
    if env_root:
        env_root = os.path.abspath(env_root)
        env_cfg = os.path.join(env_root, ".__ontobdc__", "config.yaml")
        if os.path.isfile(env_cfg):
            return env_root

    def _check_local(current_dir: str) -> Optional[str]:
        config_file: str = os.path.join(current_dir, ".__ontobdc__", "config.yaml")
        if os.path.isfile(config_file):
            return current_dir

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            return None

        return _check_local(parent_dir)

    def _check_other(current_dir: str) -> Optional[str]:
        pass

    current_dir: str = _check_local(os.path.abspath(os.getcwd()))
    if not current_dir:
        current_dir = _check_other(current_dir)
        if not current_dir:
            return None

    return current_dir


def get_script_dir() -> str:
    """
    Get the module root directory (ontobdc/).
    """
    try:
        import ontobdc
        if hasattr(ontobdc, '__path__'):
            package_path = ontobdc.__path__[0]
            return package_path
    except Exception:
        pass

    try:
        # pip show ontobdc | grep Location
        location = subprocess.check_output(["pip", "show", "ontobdc", "|", "grep", "Location"]).decode("utf-8").split(":")[1].strip()
        if location:
            return os.path.join(location, "ontobdc")
    except Exception:
        pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_root = os.path.abspath(os.path.join(script_dir, ".."))

    return module_root


def get_message_box_script() -> str:
    module_root = get_script_dir()
    candidates = [
        os.path.join(module_root, "cli", "message_box.sh"),
        os.path.abspath(os.path.join(module_root, "..", "..", "message_box.sh")),
        os.path.join(module_root, "message_box.sh"),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return os.path.join(module_root, "cli", "message_box.sh")


def get_config_dir() -> str:
    root_dir: Optional[str] = get_root_dir()
    if root_dir is None:
        return None

    return os.path.join(root_dir, ".__ontobdc__")


def config_data() -> Optional[Dict[str, Any]]:
    # Get the directory of the config file (.__ontobdc__/config.yaml)
    root_dir = get_root_dir()
    if root_dir is None:
        return None

    config_file: str = os.path.join(root_dir, ".__ontobdc__", "config.yaml")

    if not os.path.isfile(config_file):
        return None

    try:
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f) or {}
            directory = cfg.get("directory")
            if not isinstance(directory, dict):
                directory = {}
                cfg["directory"] = directory

            root = directory.get("root")
            if not isinstance(root, dict):
                root = {}
                directory["root"] = root

            if not root.get("absolute_path"):
                root["absolute_path"] = root_dir

            engine = cfg.get("engine")
            if not engine or engine not in ["venv", "colab", "docker"]:
                return None

            return cfg
    except Exception:
        return None


def check_main(args, project_root: Optional[str]):
    # Get the directory of this file (src/ontobdc/cli)
    current_dir = get_script_dir()

    check_script = os.path.join(current_dir, "check", "check.sh")

    if not os.path.exists(check_script):
        print(f"Error: check.sh not found at {check_script}")
        sys.exit(1)

    cmd = ["bash", check_script] + sys.argv[2:]

    # Execute the shell script
    try:
        env = os.environ.copy()
        if project_root:
            env["ONTOBDC_PROJECT_ROOT"] = project_root
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Error executing check script: {e}")
        sys.exit(1)


def dev_command(action, args, project_root: str):
    # Map dev commands to their scripts in src/ontobdc/dev
    current_dir = get_script_dir()
    # cli/.. -> src/ontobdc -> dev -> action.sh
    script_path = os.path.join(current_dir, "dev", f"{action}.sh")
    
    if not os.path.exists(script_path):
        print(f"Error: {action}.sh not found at {script_path}")
        sys.exit(1)

    # We need to pass all arguments to the script
    # Since we are inside python, we need to reconstruct argv
    # But args here is from argparse.
    # The simplest way is to just pass sys.argv minus the first two elements (prog name and command)
    # However, for robustness let's just use the raw arguments
    
    if len(sys.argv) > 2 and sys.argv[2] == "commit":
        cfg = config_data() or {}
        dev_tool = (cfg.get("dev") or {}).get("tool", "disabled")
        if str(dev_tool).strip() != "enabled":
            msg_box_script = get_message_box_script()
            msg = "dev.tool is not enabled in .__ontobdc__/config.yaml\n\nRun this once to fix:\n  ontobdc dev --enable-dev-tool"
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "Error", "Dev Tool Disabled", msg], check=False)
            else:
                print("Error: dev.tool is not enabled in .__ontobdc__/config.yaml")
            sys.exit(1)

        commit_script = os.path.join(current_dir, "dev", "commit.sh")
        cmd = ["bash", commit_script] + sys.argv[3:]
    else:
        cmd = [script_path] + sys.argv[2:]

    try:
        env = os.environ.copy()
        env["ONTOBDC_PROJECT_ROOT"] = project_root
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        log_script = os.path.join(current_dir, "cli", "print_log.sh")
        if os.path.exists(log_script):
            subprocess.run(["bash", log_script, "ERROR", f"Error executing {action} script: {e}"], check=False)
        else:
            print(f"Error executing {action} script: {e}")
        sys.exit(1)


def plan_command(project_root: Optional[str]):
    current_dir = get_script_dir()
    script_path = os.path.join(current_dir, "plan", "plan.sh")
    log_script = os.path.join(current_dir, "cli", "print_log.sh")

    if not os.path.exists(script_path):
        if os.path.exists(log_script):
            subprocess.run(["bash", log_script, "ERROR", f"plan.sh not found at {script_path}"], check=False)
        else:
            print(f"Error: plan.sh not found at {script_path}")
        sys.exit(1)

    cmd = ["bash", script_path] + sys.argv[2:]

    try:
        env = os.environ.copy()
        if project_root:
            env["ONTOBDC_PROJECT_ROOT"] = project_root
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except Exception as e:
        if os.path.exists(log_script):
            subprocess.run(["bash", log_script, "ERROR", f"Error executing plan script: {e}"], check=False)
        else:
            print(f"Error executing plan script: {e}")
        sys.exit(1)


def print_help():
    # Colors
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    WHITE = '\033[37m'
    
    msg_box_script = get_message_box_script()

    help_content = f"""
  {WHITE}Usage:{RESET}
    {GRAY}ontobdc{RESET} {CYAN}<command>{RESET} {GRAY}[flags/parameters]{RESET}

  {WHITE}Commands:{RESET}
    {CYAN}init{RESET}       {GRAY}Initialize ontobdc config with engine (venv|colab){RESET}
    {CYAN}check{RESET}      {GRAY}Run infrastructure checks{RESET}
    {CYAN}run{RESET}        {GRAY}Run a capability via ontobdc/run{RESET}
    {CYAN}list{RESET}       {GRAY}List all available capabilities{RESET}
    {CYAN}storage{RESET}    {GRAY}Manage storage index (list/add/remove local datasets){RESET}
"""

    config_data_obj: Optional[Dict[str, Any]] = config_data()
    if config_data_obj:
        if config_data_obj.get("entity", {}).get("framework", 'disabled') == "enabled":
            help_content += f"    {CYAN}entity{RESET}     {GRAY}Entity Framework tools{RESET}\n"
        if config_data_obj.get("dev", {}).get("tool", 'disabled') == "enabled":
            help_content += f"    {CYAN}dev{RESET}        {GRAY}Developer tools (e.g., ontobdc dev commit){RESET}\n"
    # 
    # 

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

        msg_box_script = get_message_box_script()
        
        if os.path.exists(msg_box_script):
             subprocess.run(["bash", msg_box_script, "BLUE", "OntoBDC", f"Version: {ver}", "Ontology-Based Data Capabilities"], check=False)
        else:
             print(f"OntoBDC Version: {ver}")
        sys.exit(0)

    project_root: Optional[str] = get_root_dir()

    if cmd == "init":
        from ontobdc.cli.init import init_main
        init_main()
        sys.exit(0)

    else:
        # Check if engine is installed/initialized
        current_dir = os.path.dirname(os.path.abspath(__file__))
        msg_box_script = get_message_box_script()

        cfg = config_data()

        if not cfg:
            if os.path.exists(msg_box_script):
                msg = "OntoBDC is not initialized.\n\nPlease run \033[1;37montobdc init\033[0;90m to setup the project configuration."
                subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Initialized", msg], check=False)
            else:
                print("Error: OntoBDC is not initialized. Run 'ontobdc init'.")
            sys.exit(1)

        # project_root = cfg.get("directory").get("root").get("absolute_path")
        
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
        parser.add_argument("-c", "--compact", action="store_true", help="Compact output")
        # Parse only arguments after 'check'
        args, unknown = parser.parse_known_args(sys.argv[2:])
        check_main(args, project_root)

    elif cmd == "plan":
        plan_command(project_root)

    elif cmd == "dev":
        dev_command("dev", None, project_root)

    elif cmd == "entity":
        script_dir: str = get_script_dir()
        project_script = os.path.join(script_dir, "entity", "entity.sh")
        msg_box_script = get_message_box_script()
        if not os.path.exists(project_script):
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "OntoBDC", "Error", "Entity Script Missing", f"Missing: {project_script}"], check=False)
                sys.exit(1)

        try:
            subprocess.run(["bash", project_script] + sys.argv[2:], check=False)
            sys.exit(0)
        except Exception as e:
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "OntoBDC", "Error", "Entity Execution Failed", str(e)], check=False)
            sys.exit(1)

    elif cmd == "storage":
        script_dir: str = get_script_dir()
        project_script = os.path.join(script_dir, "storage", "storage.sh")
        msg_box_script = get_message_box_script()
        if not os.path.exists(project_script):
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "OntoBDC", "Error", "Storage Script Missing", f"Missing: {project_script}"], check=False)
                sys.exit(1)

        try:
            subprocess.run(["bash", project_script] + sys.argv[2:], check=False)
            sys.exit(0)
        except Exception as e:
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "OntoBDC", "Error", "Storage Execution Failed", str(e)], check=False)
            sys.exit(1)

    else:
        print_log_script = os.path.join(current_dir, "print_log.sh")
        print("")
        subprocess.run(["bash", print_log_script, "ERROR", f"The '{cmd}' command was not found."], check=False)
        print("")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
