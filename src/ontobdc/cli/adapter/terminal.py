
import os
import re
import sys
from typing import Optional, Union, List

from ontobdc.shared.adapter.terminal_color import cursor_up, erase_line


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
            sys.stdout.write(cursor_up(rendered_lines))
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
