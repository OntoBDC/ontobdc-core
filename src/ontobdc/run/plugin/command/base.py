from typing import Callable, List, Optional

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import RunCommandResponse
from ontobdc.run.adapter.machine import IntentResolutionStateTransitionHandler
from ontobdc.run.domain.machine.state import IntentResolutionState


class RunBaseCommand(CliCommandPort, PromptChoiceAwarePort):
    """Base command for the run component.

    Accepts an explicit ``--prompt`` value, or lets the intent-resolution
    statechart ask for one (through a Textual modal, in its ``received``
    transition) when omitted. The resolved prompt is just echoed back for
    now -- capability resolution comes later.
    """

    METADATA = CliCommandMetadata(
        id="base",
        logical_component="run",
        description="Execute a capability described in natural language.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--prompt"],
                "valued": True,
                "description": (
                    "Natural-language instruction to execute. Prompted "
                    "interactively when omitted."
                ),
                "usage": 'ontobdc run --prompt "<text>"',
            },
        ],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._prompt_choice: Optional[Callable[..., str]] = None

    def set_prompt_choice(self, prompt_choice: Callable[..., str]) -> None:
        self._prompt_choice = prompt_choice

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if args == ["run"]:
            return True
        return len(args) >= 3 and args[0] == "run" and args[1] == "--prompt"

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        if not command_args:
            return True
        return (
            len(command_args) == 2
            and command_args[0] == "--prompt"
            and bool(command_args[1].strip())
        )

    def run(self) -> RunCommandResponse:
        """
        Execute the command.
        """

        command_args: List[str] = self._request.command_args
        context: CliContextPort = self._request.context
        if command_args:
            context.set_parameter_value("prompt", command_args[1])

        handler: IntentResolutionStateTransitionHandler = (
            IntentResolutionStateTransitionHandler(
                context, prompt_choice=self._prompt_choice
            )
        )
        handler.execute()

        received_result = handler.capability_results.get(
            IntentResolutionState.RECEIVED.value, {}
        )
        prompt: str = str(received_result.get("prompt") or "")

        canonical_result = handler.capability_results.get(
            IntentResolutionState.CANONICAL.value, {}
        )
        canonical_intent: str = str(canonical_result.get("canonical_intent") or "")

        parsed_result = handler.capability_results.get(
            IntentResolutionState.PARSED.value, {}
        )
        parsed_score: str = str(parsed_result.get("score") or "")

        low_confidence_result = handler.capability_results.get(
            IntentResolutionState.LOW_CONFIDENCE.value, {}
        )
        matching_capabilities = low_confidence_result.get("matching_capabilities") or []

        validated_result = handler.capability_results.get(
            IntentResolutionState.VALIDATED.value, {}
        )
        selected_capability_id = validated_result.get("selected_capability_id")

        content = {
            "prompt": prompt,
            "canonical_intent": canonical_intent,
            "parsed_score": parsed_score,
            "intent_state": handler.current_state.value.strip("_"),
        }
        if matching_capabilities:
            content["matching_capabilities"] = matching_capabilities
        if selected_capability_id:
            content["selected_capability_id"] = selected_capability_id

        return RunCommandResponse(
            title="OntoBDC Run",
            description="Received prompt.",
            content=content,
        )
