import shutil
import textwrap
try:
    from rich.console import Console
    from rich.text import Text
except Exception:
    Console = None
    Text = None

console = Console() if Console is not None else None

GRAY = "bright_black" if console is not None else "\033[0;90m"
CYAN = "cyan" if console is not None else "\033[0;36m"
YELLOW = "yellow" if console is not None else "\033[1;33m"
GREEN = "green" if console is not None else "\033[0;32m"
RED = "red" if console is not None else "\033[0;31m"
WHITE = "white" if console is not None else "\033[1;37m"
BOLD = "bold" if console is not None else "\033[1m"
RESET = "" if console is not None else "\033[0m"

def print_message_box(color: str, title_type: str, title_text: str, msg_text: str):
    if console is None or Text is None:
        print("")
        print(f"{title_type} - {title_text}")
        print(msg_text)
        print("")
        return

    # Map ANSI codes to rich styles if needed, or just assume valid rich style
    # If color starts with \033, we have a problem.
    # Simple heuristic mapping for safety:
    if "\033" in color:
        if "31" in color: color = "red"
        elif "32" in color: color = "green"
        elif "33" in color: color = "yellow"
        elif "34" in color: color = "blue"
        elif "36" in color: color = "cyan"
        elif "90" in color: color = "bright_black"
        elif "37" in color: color = "white"
        else: color = "white" # fallback

    console.print("")
    term_width = shutil.get_terminal_size().columns
    inner_width = term_width - 2
    hline = "─" * inner_width

    console.print(f"[{color}]╭{hline}╮[/{color}]")

    prefix = " >_ "
    type_formatted = f"[{BOLD} {color}]{title_type}[/{BOLD} {color}]"

    visible_len = 4 + len(title_type) + (1 + len(title_text) if title_text else 0)
    pad_len = max(0, inner_width - visible_len)
    padding = " " * pad_len

    line_content = f"[{color}]│[/{color}]{prefix}{type_formatted}"
    if title_text:
        line_content += f" {title_text}"
    line_content += f"{padding}[{color}]│[/{color}]"

    console.print(line_content)

    console.print(f"[{color}]│[/{color}]{' ' * inner_width}[{color}]│[/{color}]")

    lines = msg_text.split("\n")
    for line in lines:
        if not line:
            wrapped_lines = [" "]
        else:
            wrapped_lines = textwrap.wrap(line, width=inner_width, drop_whitespace=False)

        for wline in wrapped_lines:
            visible_len = Text.from_markup(wline).cell_len
            pad_len = max(0, inner_width - visible_len)
            padding = " " * pad_len
            console.print(
                f"[{color}]│[/{color}][{GRAY}]{wline}[/{GRAY}]{padding}[{color}]│[/{color}]"
            )

    console.print(f"[{color}]╰{hline}╯[/{color}]")
