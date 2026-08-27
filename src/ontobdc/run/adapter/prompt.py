from typing import ClassVar, List, Optional, Tuple

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Label


class RunPromptModalApp(App[Optional[str]]):
    """Standalone Textual app: a single modal asking for a natural-language
    instruction.

    Brand-styled to match :class:`ontobdc.storage.adapter.explorer.
    StorageElementExplorerApp` (same palette). Captures one line of input
    and exits immediately once submitted, returning it to the caller --
    the modal never stays on screen after the answer is captured.
    """

    TITLE: ClassVar[str] = "OntoBDC"
    SUB_TITLE: ClassVar[str] = "Run"
    CSS: ClassVar[str] = """
    Screen {
        background: #071820;
        color: #f4fbfd;
        align: center middle;
    }

    #run-prompt-modal {
        width: 60%;
        min-width: 40;
        max-width: 100;
        height: auto;
        border: round #00b4d8;
        background: #0b2630;
        padding: 1 2;
    }

    #run-prompt-question {
        color: #caf0f8;
        padding-bottom: 1;
    }

    #run-prompt-input {
        border: round #00b4d8;
    }
    """
    BINDINGS: ClassVar[List[Tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, question: str) -> None:
        super().__init__()
        self._question: str = question

    def compose(self) -> ComposeResult:
        with Vertical(id="run-prompt-modal"):
            yield Label(self._question, id="run-prompt-question")
            yield Input(placeholder="Type your instruction...", id="run-prompt-input")

    def on_mount(self) -> None:
        self.query_one("#run-prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.exit(result=event.value.strip() or None)

    def action_cancel(self) -> None:
        self.exit(result=None)


class RunPromptModalAdapter:
    """Open :class:`RunPromptModalApp` and return the captured text."""

    def open(self, question: str) -> Optional[str]:
        return RunPromptModalApp(question).run()
