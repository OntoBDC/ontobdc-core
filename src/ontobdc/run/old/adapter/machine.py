
from typing import List, Dict, Any, Optional, Type
from ontobdc.run.adapter.repository import IntentLocalStatechartRepository
from ontobdc.run.domain.machine.response import IntentScoreResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.logger import LogStrategyContainerPort, LoggerAwarePort
from sismic.model.elements import Transition
from ontobdc.run.domain.port.machine import IntentStatePort
from ontobdc.shared.adapter.context import CliContextAdapter
from ontobdc.shared.domain.port.context import CliContextPort, PromptChoiceAwarePort, PromptRawTextAwarePort
from ontobdc.run.adapter.evaluator import ContextIntentEvaluatorAdapter, DagParametersEvaluator
from ontobdc.run.domain.machine.lifecycle import RunIntentResolutionState
from ontobdc.shared.domain.port.machine import StateEvaluatorPort, StateTransitionHandlerPort
from ontobdc.shared.adapter.plugin import CapabilityLoader
from ontobdc.shared.domain.resource.capability import Capability, TransformationCapability
from ontobdc.shared.domain.resource.capability import CapabilityExecutor


class SismicIntentTransitionHandlerAdapter(StateTransitionHandlerPort):
    def __init__(self, context_graph: CliContextAdapter):
        self._context: CliContextPort = context_graph
        self._all_transitions: List[Transition] = []
        self._log_strategy : Optional[LogStrategyContainerPort] = None
        self._prompt_choice : Optional[callable] = None
        self._prompt_raw_text : Optional[callable] = None
        self._state_evaluator: StateEvaluatorPort = ContextIntentEvaluatorAdapter()

    @property
    def current_state(self) -> IntentStatePort:
        """
        Gets the current intent state of the context.
        """
        return self._state_evaluator.evaluate(context=self._context)

    @property
    def context(self) -> CliContextPort:
        """
        Returns the current CLI context managed by the transition handler.
        """
        return self._context

    @property
    def transitions(self) -> List[Transition]:
        if not self._all_transitions:
            repository = IntentLocalStatechartRepository()
            statechart = repository.get_statechart()
            self._all_transitions = list(statechart.transitions)

        return self._all_transitions

    @property
    def target_capability(self) -> Optional[Type[Capability]]:
        capability_id: Optional[str] = self._context.get_parameter_value("capability_id")
        if not isinstance(capability_id, str) or not capability_id.strip():
            return None

        return CapabilityLoader().get(capability_id)()

    @property
    def is_successful(self) -> bool:
        """
        Indicates if the current state is successful.
        """
        return self.current_state in [RunIntentResolutionState.FILLED]

    @property
    def is_unresolvable(self) -> bool:
        """
        Indicates if the current state is unresolvable.
        """
        return self.current_state in [RunIntentResolutionState.UNREACHABLE]

    @property
    def intent(self) -> Optional[str]:
        """
        Gets the current intent of the context.
        """
        return self._context.get_parameter_value("user_intent")

    def intent_score_is_sufficient(self) -> bool:
        """
        Checks if the intent score is sufficient.
        """
        intent_score: Optional[float] = self._context.get_parameter_value("intent_score")
        if not intent_score:
            return False

        return intent_score >= IntentScoreResponse.INTENT_SCORE_THRESHOLD

    def intent_score_is_insufficient(self) -> bool:
        """
        Checks if the intent score is insufficient.
        """
        return not self.intent_score_is_sufficient()

    def execution_plan_is_valid(self) -> bool:
        """
        Checks if the execution plan is valid.

        A valid plan is one whose target capability is already defined and whose
        required parameters can be satisfied, either directly from the current
        context or through the available support capabilities.
        """
        capability_id: Optional[str] = self._context.get_parameter_value("capability_id")
        if not capability_id:
            return False

        if not DagParametersEvaluator(self._context).evaluate():
            return False

        return True

    def execution_plan_is_unreachable(self) -> bool:
        """
        Checks if the execution plan is unreachable.

        Unlike a valid plan, an unreachable plan already has a target capability
        defined but fails DAG parameter evaluation, meaning the current context
        does not provide enough information to resolve the required inputs.
        """
        capability_id: Optional[str] = self._context.get_parameter_value("capability_id")
        if not capability_id:
            return False

        return not DagParametersEvaluator(self._context).evaluate()

    def set_log_strategy(self, log_strategy: LogStrategyContainerPort):
        self._log_strategy = log_strategy

    def set_prompt_choice(self, prompt_choice: callable):
        self._prompt_choice = prompt_choice

    def set_prompt_raw_text(self, prompt_raw_text: callable):
        self._prompt_raw_text = prompt_raw_text

    def can_transit_from(self, from_state: IntentStatePort) -> bool:
        """
        Checks if the transition is valid.
        """
        if self.current_state != from_state:
            return False

        for transition in self.transitions:
            source: IntentStatePort = RunIntentResolutionState.get_state(transition.source)

            if source == self.current_state:
                # print(source)
                return True

        raise NotImplementedError(f"Invalid transition from {self.current_state} to {from_state} with source {print(source)}")
        return False

    def can_transit_to(self, to_state: IntentStatePort) -> bool:
        """
        Checks if the transition is valid.
        """
        if self.current_state == to_state:
            return False

        for transition in self.transitions:
            source: IntentStatePort = RunIntentResolutionState.get_state(transition.source)
            target: IntentStatePort = RunIntentResolutionState.get_state(transition.target)

            if source == self.current_state and target == to_state:
                return True

        return False

    def validate_state_transition(self, from_state: IntentStatePort, to_state: IntentStatePort) -> bool:
        """
        Validates if the transition happened correctly.
        """
        if from_state == to_state:
            return False

        return True

    def perform_state_transition(self, to_state: IntentStatePort = None, from_state: IntentStatePort = None) -> None:
        if to_state:
            self._perform_state_transition_to(to_state)
            return
        elif from_state:
            self._perform_state_transition_from(from_state)
            return

        raise ValueError("No state transition specified.")

    def _perform_state_transition_to(self, to_state: IntentStatePort) -> None:
        """
        Performs a state transition to the specified state.
        """
        state_name = to_state.value.strip("_")

        target_id = f"org.ontobdc.run.plugin.capability.resolution.target.{state_name}"

        for capability_class in CapabilityLoader().get_all("capability"):
            if capability_class.METADATA.id == target_id:
                try:
                    capability: TransformationCapability = capability_class()
                    if isinstance(capability, LoggerAwarePort):
                        capability.set_log_strategy(self._log_strategy)

                    if isinstance(capability, PromptChoiceAwarePort):
                        capability.set_prompt_choice(self._prompt_choice)

                    if isinstance(capability, PromptRawTextAwarePort):
                        capability.set_prompt_raw_text(self._prompt_raw_text)

                    result: Dict[str, Any] = CapabilityExecutor.execute(capability, self._context)
                    self._context = result["cli_context"]
                    return
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to transition context to '{to_state.value.strip('_')}' due to error: {str(exc)}"
                    ) from exc

        raise RuntimeError(
            f"No transition capability found for state '{to_state.value.strip('_')}'"
        )

    def _perform_state_transition_from(self, from_state: IntentStatePort) -> None:
        """
        Performs a state transition from the specified state.
        """
        state_name = from_state.value.strip("_")

        source_id = f"org.ontobdc.run.plugin.capability.resolution.from.{state_name}"

        for capability_class in CapabilityLoader().get_all("capability"):
            if capability_class.METADATA.id == source_id:
                try:
                    capability: TransformationCapability = capability_class()
                    if isinstance(capability, LoggerAwarePort):
                        capability.set_log_strategy(self._log_strategy)

                    if isinstance(capability, PromptChoiceAwarePort):
                        capability.set_prompt_choice(self._prompt_choice)

                    if isinstance(capability, PromptRawTextAwarePort):
                        capability.set_prompt_raw_text(self._prompt_raw_text)

                    result: Dict[str, Any] = CapabilityExecutor.execute(capability, self._context)
                    self._context = result["cli_context"]
                    return
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to transition context from '{from_state.value.strip('_')}' due to error: {str(exc)}"
                    ) from exc

        raise RuntimeError(
            f"No transition capability found for state '{from_state.value.strip('_')}'"
        )
