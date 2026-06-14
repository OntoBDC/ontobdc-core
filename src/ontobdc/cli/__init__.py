
import os
import sys
import json
from ontobdc.cli.adapter.command import CliCommandRunAdapter
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, ExceptionCommandResponse, HelpCommandResponse
from ontobdc.shared.domain.port.context import PromptChoiceAwarePort, PromptRawTextAwarePort
from ontobdc.shared.domain.port.logger import LoggerAwarePort
from ontobdc.shared.domain.resource.logger import LogLevel, LogStrategyResource, NullLogRepository
import yaml
import argparse
import subprocess
from typing import Any, Dict, List, Optional
from ontobdc.cli.init import log as print_log, prompt_choice, prompt_raw_text


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
            msg = " The dev.tool is not enabled\n\n Run this once to fix:\n   ontobdc dev --enable-dev-tool"
            if os.path.exists(msg_box_script):
                subprocess.run(["bash", msg_box_script, "RED", "Error", "Dev Tool Disabled", msg], check=False)
            else:
                print("Error: The dev.tool is not enabled")
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


def ontobdc_data() -> Dict[str, Any]:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pyproject_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "pyproject.toml"))

    if not os.path.isfile(pyproject_path):
        return {}

    try:
        try:
            import tomllib  # Python 3.11+
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        # Normalize through JSON to ensure the result only contains JSON-safe types.
        return json.loads(json.dumps(data))
    except Exception:
        return {}


def command_help_message(command_name: str, title_text: str) -> str:
    bold = '\033[1m'
    reset = '\033[0m'
    white = '\033[37m'
    gray = '\033[90m'

    ontobdc_meta = ((ontobdc_data().get("tool") or {}).get("ontobdc") or {})
    command_meta = ((ontobdc_meta.get("commands") or {}).get(command_name) or {})

    usage_entries = command_meta.get("usage") or [f"ontobdc {command_name}"]
    description = str(command_meta.get("description") or "").strip() or "No description available."
    options = command_meta.get("options") or []
    notes = command_meta.get("notes") or []

    usage_block = "\n".join(f"    {gray}{entry}{reset}" for entry in usage_entries)
    options_block = "\n".join(f"    {gray}{entry}{reset}" for entry in options)
    notes_block = "\n".join(f"    {gray}{entry}{reset}" for entry in notes)

    help_content = (
        f"\n  {bold}{white}Usage:{reset}\n"
        f"{usage_block}\n\n"
        f"  {bold}{white}Description:{reset}\n"
        f"    {gray}{description}{reset}"
    )

    if options_block:
        help_content += f"\n\n  {bold}{white}Options:{reset}\n{options_block}"

    if notes_block:
        help_content += f"\n\n  {bold}{white}Notes:{reset}\n{notes_block}"

    return help_content


def render_command_help(command_name: str, title_text: str) -> None:
    msg_box_script = get_message_box_script()
    help_content = command_help_message(command_name, title_text)

    if os.path.exists(msg_box_script):
        subprocess.run(["bash", msg_box_script, "INFO", "OntoBDC", title_text, help_content], check=False)
    else:
        print(help_content)


def print_help():
    # Colors
    BOLD = '\033[1m'
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GRAY = '\033[90m'
    WHITE = '\033[37m'
    
    msg_box_script = get_message_box_script()
    ontobdc_meta = ((ontobdc_data().get("tool") or {}).get("ontobdc") or {})
    commands_meta = ontobdc_meta.get("commands") or {}
    config_data_obj: Optional[Dict[str, Any]] = config_data()
    cli_meta = commands_meta.get("cli") or {}

    executable_name = "ontobdc"
    cli_usage = cli_meta.get("usage")
    if isinstance(cli_usage, list) and cli_usage:
        first_usage = str(cli_usage[0]).strip()
        if first_usage:
            executable_name = first_usage.split()[0]

    command_rows = []
    for command_name, command_meta in commands_meta.items():
        if command_name == "cli" or not isinstance(command_meta, dict):
            continue

        availability = str(command_meta.get("availability", "")).lower()
        if "dev.tool enabled" in availability:
            if not config_data_obj or config_data_obj.get("dev", {}).get("tool", "disabled") != "enabled":
                continue
        elif "a3 enabled" in availability:
            if not config_data_obj or config_data_obj.get("a3", {}).get("framework", "disabled") != "enabled":
                continue

        description = str(command_meta.get("description", "")).strip() or "No description available."
        command_rows.append((command_name, description))

    command_width = max((len(command_name) for command_name, _ in command_rows), default=0)
    commands_block = "\n".join(
        f"    {CYAN}{command_name}{RESET}{' ' * (command_width - len(command_name) + 2)}{GRAY}{description}{RESET}"
        for command_name, description in command_rows
    )

    help_content = f"""
  {BOLD}{WHITE}Usage:{RESET}
    {GRAY}{executable_name}{RESET} {CYAN}<command>{RESET} {GRAY}[flags/parameters]{RESET}

  {WHITE}Commands:{RESET}
{commands_block}
"""

    if os.path.exists(msg_box_script):
         subprocess.run(["bash", msg_box_script, "INFO", "OntoBDC", "CLI Help", help_content], check=False)
    else:
        print("")
        print(f"{WHITE}OntoBDC CLI{RESET}")
        print(help_content)
        print("")


def _render_response(response: CommandResponse, render_type: str) -> None:
    if isinstance(response, HelpCommandResponse):
        print(response)
    else:
        print(response)


def _check_command(cli_command_run: CliCommandPort, incoming_args: List[str]) -> bool:
    # The CliCommandRunAdapter.make() already:
    # 1. Validated the arguments
    # 2. Created the command instance
    # 3. Called cmd_instance.check() and only returned if it passed
    # So most of the work is already done!
    # We'll just trust that make() did its job, but we still return True
    # to maintain the same flow in main()
    return True


def main():
    try:
        incoming_args: List[str] = [arg for arg in sys.argv[1:] if arg != "--json"]
        render_type = 'json' if "--json" in sys.argv else 'rich'
        cli_command_run: CliCommandPort = CliCommandRunAdapter.make(incoming_args)
        if _check_command(cli_command_run, incoming_args):
            if isinstance(cli_command_run, LoggerAwarePort):
                log_strategy = LogStrategyResource(
                    print_log=print_log,
                    log_level=LogLevel.INFORMATIONAL,
                    log_repository=NullLogRepository(),
                )
                cli_command_run.set_log_strategy(log_strategy)

            if isinstance(cli_command_run, PromptChoiceAwarePort):
                cli_command_run.set_prompt_choice(prompt_choice)

            if isinstance(cli_command_run, PromptRawTextAwarePort):
                cli_command_run.set_prompt_raw_text(prompt_raw_text)

            response: CommandResponse = cli_command_run.run()
            _render_response(response, render_type)
            sys.exit(0)
    except CliCommandArgumentException as e:
        if sys.argv[1] not in ["list", "init", "dev", "check"]:
            response = ExceptionCommandResponse(
                title=str(e).split(":")[0].strip(),
                description=f"{str(e)}",
                content={
                    "execution_response": str(e),
                },
            )
            _render_response(response, render_type)
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

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

    command_help_titles = {
        "check": "Check Help",
        "context": "Context Help",
        "list": "List Help",
        "run": "Run Help",
        "storage": "Storage Help",
        "dev": "Dev Help",
        "a3": "A3 Help",
    }

    if cmd in command_help_titles and any(arg in ("-h", "--help", "help") for arg in sys.argv[2:]):
        render_command_help(cmd, command_help_titles[cmd])
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
                msg = " OntoBDC is not initialized.\n\n Please run \033[1;37montobdc init\033[0m to setup the project configuration."
                subprocess.run(["bash", msg_box_script, "RED", "Error", "Not Initialized", msg], check=False)
            else:
                print("Error: OntoBDC is not initialized. Run 'ontobdc init'.")
            sys.exit(1)

        
    if cmd == "list":
        try:
            from ontobdc.list.list import main as list_main
        except ImportError:
            list_main = None
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
        args, _ = parser.parse_known_args(sys.argv[2:])
        check_main(args, project_root)

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
