import os
import re
import sys
import argparse
import json
from typing import List, Optional, Union
import yaml
import subprocess
from importlib.metadata import version, PackageNotFoundError


def is_extra_enabled(extra_name: str) -> bool:
    """
    Checks if all dependencies defined in a specific 'extra' 
    of pyproject.toml are installed.
    """
    current_dir = os.path.dirname(__file__)
    # Navigate to the project root (cli -> ontobdc -> src -> root)
    pyproject_path = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "pyproject.toml"))
    
    if not os.path.exists(pyproject_path):
        return False
        
    deps = []
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Search for the dependency list in the `<extra_name> = [...]` block
            pattern = rf'{extra_name}\s*=\s*\[(.*?)\]'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                deps_text = match.group(1)
                # Extract package names ignoring double or single quotes
                deps = re.findall(r'"([^"]+)"', deps_text)
                deps.extend(re.findall(r"'([^']+)'", deps_text))
                
    except Exception:
        return False

    # If no dependencies were found, consider it disabled
    if not deps:
        return False

    # Verify the installation of each package using importlib.metadata
    for dep in deps:
        # Remove version specifiers if they exist (e.g., pytest>=7.0 -> pytest)
        pkg_name = re.split(r'[=><~]', dep)[0].strip()
        try:
            version(pkg_name)
        except PackageNotFoundError:
            return False
            
    return True


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


def init_help_message() -> str:
    try:
        from ontobdc.cli import ontobdc_data

        ontobdc_meta = ((ontobdc_data().get("tool") or {}).get("ontobdc") or {})
        init_meta = (ontobdc_meta.get("commands") or {}).get("init") or {}
    except Exception:
        init_meta = {}

    bold = "\033[1m"
    reset = "\033[0m"
    white = "\033[37m"
    gray = "\033[90m"

    usage_entries = init_meta.get("usage") or [
        "ontobdc init <engine>",
        "ontobdc init",
        "ontobdc init -h | --help",
    ]
    description = str(
        init_meta.get("description") or "Initialize the local OntoBDC project configuration."
    ).strip()
    options = init_meta.get("options") or [
        "engine: explicit execution engine such as venv or colab",
    ]
    notes = init_meta.get("notes") or []

    usage_block = "\n".join(f"    {gray}{entry}{reset}" for entry in usage_entries)
    options_block = "\n".join(f"    {gray}{entry}{reset}" for entry in options)
    notes_block = "\n".join(f"    {gray}{entry}{reset}" for entry in notes)

    help_content = (
        f"\n  {bold}{white}Usage:{reset}\n"
        f"{usage_block}\n\n"
        f"  {bold}{white}Description:{reset}\n"
        f"    {gray}{description}{reset}\n\n"
        f"  {bold}{white}Options:{reset}\n"
        f"{options_block}"
    )

    if notes_block:
        help_content += f"\n\n  {bold}{white}Notes:{reset}\n{notes_block}"

    return help_content


def init_engine_main():
    """
    Initialize OntoBDC configuration.
    Creates .__ontobdc__ directory and config.yaml with specified engine.
    """
    if any(arg in ("-h", "--help") for arg in sys.argv[2:]):
        message_box("INFO", "OntoBDC", "Init Help", init_help_message())
        return

    parser = argparse.ArgumentParser(description="Initialize OntoBDC configuration")
    parser.add_argument("engine", nargs="?", help="Execution engine (e.g. venv, colab). If omitted, attempts auto-detection.")
    
    # We only parse arguments relevant to init
    args, _ = parser.parse_known_args(sys.argv[2:])
    
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
                valid_engines = data.get('config', {}).get('engine', [])
        except Exception as e:
            log("WARN", f"Failed to load config.json validation: {e}")
    
    if valid_engines and engine not in valid_engines:
        log("ERROR", f"Invalid engine '{engine}'.")
        print(f"Valid engine are: {', '.join(valid_engines)}")
        sys.exit(1)

    # 2. Create .__ontobdc__ directory in current working directory
    cwd = os.getcwd()
    ontobdc_dir = os.path.join(cwd, ".__ontobdc__")
    config_file = os.path.join(ontobdc_dir, "config.yaml")

    if os.path.exists(config_file):
        message_box("YELLOW", "Warning", "Already Initialized", " OntoBDC is already initialized in this directory.")
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
    config_data.setdefault('directory', {}).setdefault('root', {})['absolute_path'] = cwd
    
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
        check_main(CheckArgs(), cwd)
    except SystemExit:
        # check_main calls sys.exit, we catch it to not crash if check fails but init succeeded
        pass


def init_main():
    init_engine_main()


def prompt_choice(
    title_or_question: str,
    question_or_options: Union[str, List[str]],
    options: Optional[List[str]] = None,
    default: Optional[str] = None,
    language: str = "en",
    none: Optional[str] = None,
) -> str:
    """
    Prompt the user to choose from a list of options.
    Args:
        title_or_question: The title of the prompt or the question in legacy mode.
        question_or_options: The question to ask or the options in legacy mode.
        options: A list of options to choose from.
        default: The option selected by default.
        language: Prompt language.
        none: Optional label for an extra "none/exit" option.
    Returns:
        The user's choice.
    """
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.text import Text

    if isinstance(question_or_options, list):
        title = "Context"
        question = title_or_question
        prompt_options = list(question_or_options)
    else:
        title = title_or_question
        question = question_or_options
        prompt_options = list(options or [])

    if none:
        prompt_options.append(none)

    if not prompt_options:
        raise ValueError("options must not be empty")

    def option_value(label: str) -> str:
        match = re.search(r"\(([^()]+)\)\s*$", label)
        if match:
            return match.group(1).strip()
        return label

    option_values = [option_value(option) for option in prompt_options]
    default_choice = prompt_options[0]
    if default:
        for option_label, option_id in zip(prompt_options, option_values):
            if default in (option_label, option_id):
                default_choice = option_label
                break

    interactive_hint = {
        "pt": [("Use as setas para cima/baixo e ", "grey50"), ("Enter", "bold white"), (".", "grey50")],
        "pt": [("Use as setas para cima/baixo e ", "grey50"), ("Enter", "bold white"), (".", "grey50")],
    }.get(
        language,
        [("Use up/down arrows and ", "grey50"), ("Enter", "bold white"), (".", "grey50")],
    )

    type_hint = {
        "pt": "Digite uma opcao e pressione Enter.",
        "pt": "Digite uma opcao e pressione Enter.",
    }.get(language, "Type an option and press Enter.")

    def render_panel(selected: Optional[int] = None, interactive: bool = False) -> str:
        lines: List[Text] = [
            Text.assemble(
                (">_ ", "default"),
                ("OntoBDC", "bold blue"),
                (f" {title} Prompt", "bold white"),
            ),
            Text(""),
            Text(question, style="grey70"),
            Text(""),
        ]

        for idx, label in enumerate(prompt_options):
            if selected is None:
                lines.append(Text(f"  {label}", style="grey70"))
            elif idx == selected:
                lines.append(Text.assemble(("  ➜ ", "cyan"), (label, "cyan bold")))
            else:
                lines.append(Text(f"    {label}", style="grey70"))

        lines.append(Text(""))
        if interactive:
            lines.append(Text.assemble(*interactive_hint))
        else:
            lines.append(Text(type_hint, style="grey50"))

        group = Group(*lines)
        console = Console()
        with console.capture() as capture:
            console.print(
                Panel(
                    group,
                    border_style="grey50",
                    expand=True,
                )
            )
        return capture.get()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stdout.write(render_panel())
        sys.stdout.flush()
        try:
            answer = input("> ").strip()
        except EOFError:
            return option_value(default_choice)

        if not answer:
            return option_value(default_choice)

        normalized = {}
        for option_label, option_id in zip(prompt_options, option_values):
            normalized[option_label.lower()] = option_id
            normalized[option_id.lower()] = option_id

        return normalized.get(answer.lower(), option_value(default_choice))

    import select
    import termios
    import tty

    default_index = prompt_options.index(default_choice)
    selected = default_index
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    rendered_lines = 0

    def render() -> None:
        nonlocal rendered_lines
        panel = render_panel(selected=selected, interactive=True)
        if rendered_lines:
            sys.stdout.write(f"\033[{rendered_lines}A")
        sys.stdout.write(panel)
        sys.stdout.flush()
        rendered_lines = panel.count("\n")

    try:
        tty.setcbreak(fd)
        render()
        while True:
            ch = os.read(fd, 1)
            if not ch:
                continue
            if ch in (b"\n", b"\r"):
                return option_values[selected]
            if ch == b"\x1b":
                r, _, _ = select.select([fd], [], [], 1.0)
                if not r:
                    return option_value(default_choice)

                nxt = os.read(fd, 1)
                if nxt not in (b"[", b"O"):
                    continue

                seq = b""
                for _ in range(16):
                    r, _, _ = select.select([fd], [], [], 0.02)
                    if not r:
                        break
                    seq += os.read(fd, 1)

                if not seq:
                    continue

                code = seq[-1:]
                if code == b"A":
                    selected = (selected - 1) % len(prompt_options)
                elif code == b"B":
                    selected = (selected + 1) % len(prompt_options)
                else:
                    continue
                render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def prompt_raw_text(
    title_or_question: str,
    question: Optional[str] = None,
    default: Optional[str] = None,
    language: str = "en",
) -> str:
    """
    Prompt the user for free-form text input.
    """
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.text import Text

    if question is None:
        title = "Context"
        prompt_question = title_or_question
    else:
        title = title_or_question
        prompt_question = question

    type_hint = {
        "pt": [
            ("Digite sua resposta e pressione ", "grey50"),
            ("Enter", "bold white"),
            (" para enviar ou ", "grey50"),
            ("Esc", "bold white"),
            (" para sair.", "grey50"),
        ],
        "pt_BR": [
            ("Digite sua resposta e pressione ", "grey50"),
            ("Enter", "bold white"),
            (" para enviar ou ", "grey50"),
            ("Esc", "bold white"),
            (" para sair.", "grey50"),
        ],
    }.get(
        language,
        [
            ("Type your answer and press ", "grey50"),
            ("Enter", "bold white"),
            (" to send or ", "grey50"),
            ("Esc", "bold white"),
            (" to exit.", "grey50"),
        ],
    )

    def render_panel() -> str:
        lines: List[Text] = [
            Text.assemble(
                (">_ ", "default"),
                ("OntoBDC", "bold blue"),
                (f" {title} Prompt", "bold white"),
            ),
            Text(""),
            Text(prompt_question, style="grey70"),
            Text(""),
        ]

        lines.append(Text.assemble(*type_hint))

        group = Group(*lines)
        console = Console()
        with console.capture() as capture:
            console.print(
                Panel(
                    group,
                    border_style="grey50",
                    expand=True,
                )
            )
        return capture.get()

    sys.stdout.write(render_panel())
    sys.stdout.flush()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        try:
            answer = input("> ").strip()
        except EOFError:
            return default or ""
        return answer or (default or "")

    import codecs
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    decoder = codecs.getincrementaldecoder("utf-8")()
    answer_chars: List[str] = []

    def render_input() -> None:
        sys.stdout.write("\r\033[2K> " + "".join(answer_chars))
        sys.stdout.flush()

    try:
        tty.setcbreak(fd)
        render_input()
        while True:
            chunk = os.read(fd, 1)
            if not chunk:
                continue

            if chunk in (b"\n", b"\r"):
                sys.stdout.write("\n")
                return "".join(answer_chars).strip() or (default or "")

            if chunk == b"\x1b":
                r, _, _ = select.select([fd], [], [], 0.03)
                if not r:
                    sys.stdout.write("\n")
                    return default or ""

                while True:
                    r, _, _ = select.select([fd], [], [], 0.01)
                    if not r:
                        break
                    os.read(fd, 1)
                continue

            if chunk in (b"\x7f", b"\b"):
                if answer_chars:
                    answer_chars.pop()
                    render_input()
                continue

            try:
                char = decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                continue

            if char:
                answer_chars.append(char)
                render_input()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
