from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort, PromptChoiceAwarePort
from ontobdc.run.domain.machine.state import IntentResolutionState
from ontobdc.run.domain.port.machine import (
    IntentResolutionStateEvaluatorPort,
    IntentResolutionStatePort,
    IntentResolutionStateTransitionHandlerPort,
)
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort

# Matches the original design's IntentScoreResponse.INTENT_SCORE_THRESHOLD.
INTENT_SCORE_THRESHOLD: float = 0.8


class IntentResolutionStateEvaluatorAdapter(IntentResolutionStateEvaluatorPort):
    """No intent-resolution session is persisted anywhere yet, so every
    run currently starts undefined -- this will inspect real session
    state once one exists to observe.
    """

    @property
    def process_state_class(self) -> Type[IntentResolutionStatePort]:
        return IntentResolutionState

    def evaluate(self, context: CliContextPort) -> IntentResolutionStatePort:
        return IntentResolutionState.UNDEFINED


class IntentResolutionStateTransitionHandler(IntentResolutionStateTransitionHandlerPort):
    # Every state past "received" shares that one capability's per-prompt
    # ETL directory. Lending its concrete path under this parameter name
    # (see `perform_state_transition`) lets each downstream capability
    # locate its own state file *and* read whatever real data it needs
    # (prompt text, canonical intent, prior matches) straight from sibling
    # state files -- never by threading raw values through `context`.
    _RUN_STATE_DIRECTORY_PARAMETER: str = "run_state_directory"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        prompt_choice: Optional[Callable[..., str]] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._prompt_choice: Optional[Callable[..., str]] = prompt_choice
        self._state_evaluator: IntentResolutionStateEvaluatorPort = (
            IntentResolutionStateEvaluatorAdapter()
        )
        self._active_state: Optional[IntentResolutionStatePort] = None
        self._capability_results: Dict[str, Dict[str, Any]] = {}

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def capability_results(self) -> Dict[str, Dict[str, Any]]:
        """Each transition's capability output, keyed by the target state's
        raw value (e.g. ``"__received__"``).

        Capabilities communicate their outcome through this in-memory map
        instead of writing run-specific values (like the captured prompt)
        into ``context`` -- ``context`` stays for durable/cross-process
        state (root path, language, ...), not per-run scratch data.
        """
        return dict(self._capability_results)

    @property
    def current_state(self) -> IntentResolutionStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> IntentResolutionStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[IntentResolutionStatePort]:
        return list(IntentResolutionState)

    def can_transit_to(self, to_state: IntentResolutionStatePort) -> bool:
        return self.current_state != to_state

    def intent_score_is_sufficient(self) -> bool:
        # Reached from three different states, each with its own notion of
        # "sufficient": from "parsed" it means the parsed score itself
        # cleared the threshold; from "low_confidence" or "matched" it
        # means that state already resolved successfully (matched at least
        # one capability by tag) -- either capability raises instead of
        # writing a result when it can't, so a present result there is
        # itself the signal.
        if self.current_state in (
            IntentResolutionState.LOW_CONFIDENCE,
            IntentResolutionState.MATCHED,
        ):
            return bool(self._capability_results.get(self.current_state.value))

        return not self.intent_score_is_insufficient()

    def intent_score_is_insufficient(self) -> bool:
        parsed_result: Dict[str, Any] = self._capability_results.get(
            IntentResolutionState.PARSED.value, {}
        )
        score: Any = parsed_result.get("score")
        if not isinstance(score, (int, float)):
            return True

        return score < INTENT_SCORE_THRESHOLD

    def perform_state_transition(self, to_state: IntentResolutionStatePort) -> None:
        observed_state: IntentResolutionStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"Run intent resolution transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.run.plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Run intent resolution capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        if isinstance(capability, PromptChoiceAwarePort):
            if self._prompt_choice is None:
                raise RuntimeError(
                    f"Capability '{capability_id}' needs a prompt choice "
                    "function, but none was configured on this handler."
                )
            capability.set_prompt_choice(self._prompt_choice)

        # Every capability only ever receives `context`, so "received"'s
        # ETL directory (kept in-memory on this handler, never persisted --
        # see `capability_results`) is lent to `context` just for this one
        # transition, then always removed in `finally`, even if the
        # capability raises. This keeps context.ttl clean the same way
        # `PromptReceivedCapability` itself does when reading an explicit
        # --prompt -- and, unlike lending raw values, never needs extending
        # when a later capability needs a new piece of upstream data: it
        # just reads the sibling state file itself from this directory.
        lent_parameters: Dict[str, Any] = {}
        received_result: Dict[str, Any] = self._capability_results.get(
            IntentResolutionState.RECEIVED.value, {}
        )
        received_state_path: Any = received_result.get("state_path")
        if received_state_path:
            run_state_directory: str = str(Path(received_state_path).parent)
            self._context.set_parameter_value(
                self._RUN_STATE_DIRECTORY_PARAMETER, run_state_directory
            )
            lent_parameters[self._RUN_STATE_DIRECTORY_PARAMETER] = run_state_directory

        try:
            result: Dict[str, Any] = CapabilityExecutor.execute(capability, self._context)
        finally:
            for parameter_name in lent_parameters:
                self._context.delete_parameter(parameter_name)

        self._capability_results[to_state.value] = result

    def validate_state_transition(
        self,
        from_state: IntentResolutionStatePort,
        to_state: IntentResolutionStatePort,
    ) -> bool:
        return from_state != to_state

    def execute(self) -> List[str]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=IntentResolutionState,
            state_context_name="IntentResolutionStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        # "parsed"'s two outgoing guards are exhaustive and mutually
        # exclusive (intent_score_is_sufficient() XOR intent_score_is_
        # insufficient()), and "low_confidence"'s and "matched"'s single
        # outgoing guard is only ever evaluated after their own capability
        # already ran and populated a result (that capability raises
        # instead of writing one when it can't resolve a match, aborting
        # the walk before the guard is ever reached) -- so every guard past
        # "parsed" is always decidable and exactly one transition fires at
        # each step. A single continuous walk to "validated" is therefore
        # safe: unlike a state with only one *conditional* transition, this
        # never risks StateWorkerAdapter's stuck-state detection (which
        # fires when an execute_once() call changes nothing).
        return worker.work(stop_state=IntentResolutionState.VALIDATED)

    def _get_statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            __file__,
            "standard_intent_resolution.yaml",
        )

    def bind_active_state(self, state: IntentResolutionStatePort) -> None:
        self._active_state = state
