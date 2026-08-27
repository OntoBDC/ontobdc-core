from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.run.adapter.prompt import RunPromptModalAdapter
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.util import generate_hash
from ontobdc.shared.domain.model.capability import CapabilityMetadata

METADATA_DIRECTORY = ".__ontobdc__"
ETL_DIRECTORY = "etl"
RUN_ETL_DIRECTORY = "run"
STATE_EXTENSION = "txt"


class PromptReceivedCapability(TransactionCapability):
    """Ensure a natural-language prompt is present, asking for one through
    the Textual modal when it was not supplied via ``--prompt``, and
    persist it as the RECEIVED ETL state artifact.

    The prompt is deliberately not written to ``context`` -- that mirrors
    ``DataGatheredCapability``'s pattern of materializing a transition's
    outcome as a state artifact under ``.__ontobdc__/etl/...`` instead of
    stashing per-run scratch data on the shared context object. The
    captured value is still made available to the calling command through
    ``IntentResolutionStateTransitionHandler.capability_results``.

    The state artifact's *directory* is named after a hash of the prompt
    (so distinct prompts don't collide, and the same prompt run twice
    lands on the same directory); the *file* inside it is always named
    after the state itself (``__received__.txt``), matching
    ``DataGatheredCapability``'s ``<state value>.<extension>`` convention.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.run.plugin.capability.transformation.target."
            "received"
        ),
        version="1.0.0",
        name="Prompt Received",
        description=(
            "Capture the natural-language prompt driving this run, asking "
            "interactively when it was not provided."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["run", "prompt", "intent"],
        supported_languages=["en", "pt-br"],
    )

    _PROMPT_QUESTIONS: Dict[str, str] = {
        "en": "What do you need?",
        "pt": "Em que posso ajudar?",
        "pt-br": "Em que posso ajudar?",
        "pt-pt": "Em que posso ajudar?",
    }

    def __init__(
        self,
        prompt_modal_adapter: Optional[RunPromptModalAdapter] = None,
    ) -> None:
        self._prompt_modal_adapter: RunPromptModalAdapter = (
            prompt_modal_adapter or RunPromptModalAdapter()
        )
        self._captured_prompt: Optional[str] = None

    @property
    def metadata(self) -> CapabilityMetadata:
        # CapabilityExecutor reads `metadata.log_message` only *after*
        # execute() returns, so by then `_captured_prompt` is set and this
        # override can hand back a METADATA copy whose log_message embeds
        # the actual prompt -- log_message itself stays static text (no
        # templating support), so the interpolation has to happen here
        # instead. Before execute() runs (resolve_inputs/check_inputs),
        # this still returns the plain METADATA declared above.
        if self._captured_prompt is None:
            return self.METADATA

        return self.METADATA.model_copy(
            update={
                "log_message": {
                    "info": {
                        "en": f"The prompt was received: {self._captured_prompt}",
                        "pt-br": f"O prompt foi recebido: {self._captured_prompt}",
                    },
                },
            },
        )

    def label(self, lang: str = "en") -> str:
        return IntentResolutionState.RECEIVED.label(lang)

    def description(self, lang: str = "en") -> str:
        return IntentResolutionState.RECEIVED.description(lang)

    @classmethod
    def state_directory(cls, context: CliContextPort, prompt: str) -> Path:
        return (
            Path(str(context.root_path)).expanduser().resolve()
            / METADATA_DIRECTORY
            / ETL_DIRECTORY
            / RUN_ETL_DIRECTORY
            / generate_hash({"prompt": prompt})
        )

    @classmethod
    def state_path(cls, context: CliContextPort, prompt: str) -> Path:
        return cls.state_directory(context, prompt) / (
            f"{IntentResolutionState.RECEIVED.value}.{STATE_EXTENSION}"
        )

    def check(self, context: CliContextPort, prompt: str) -> bool:
        try:
            path = self.state_path(context, prompt)
            if not path.is_file():
                return False
            return bool(path.read_text(encoding="utf-8").strip())
        except OSError:
            return False

    def is_satisfied(self, context: CliContextPort, prompt: str) -> bool:
        return self.check(context, prompt)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        # `context` is the only channel RunBaseCommand has to hand in an
        # explicit --prompt value, but CliContextPort persists parameters
        # to context.ttl across invocations -- read it, then delete it
        # immediately so a --prompt from one run is never silently reused
        # by a later bare `ontobdc run` that should have opened the modal.
        prompt: str = str(context.get_parameter_value("prompt") or "").strip()
        context.delete_parameter("prompt")
        if not prompt:
            question: str = self._PROMPT_QUESTIONS.get(
                context.language, self._PROMPT_QUESTIONS["en"]
            )
            prompt = str(self._prompt_modal_adapter.open(question) or "").strip()
            if not prompt:
                raise ValueError("Prompt cannot be empty.")

        state_path: Path = self.state_path(context, prompt)
        if not self.is_satisfied(context, prompt):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(prompt, encoding="utf-8")

        self._captured_prompt = prompt
        return {"prompt": prompt, "state_path": str(state_path)}
