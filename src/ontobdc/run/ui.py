import shutil
import textwrap
from rich.console import Console
from rich.text import Text

console = Console()

GRAY = "bright_black"
CYAN = "cyan"
YELLOW = "yellow"
GREEN = "green"
RED = "red"
WHITE = "white"
BOLD = "bold"

def print_message_box(color: str, title_type: str, title_text: str, msg_text: str):
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
