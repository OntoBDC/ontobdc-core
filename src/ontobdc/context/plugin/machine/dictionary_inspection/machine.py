from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional
from pathlib import Path

import yaml

from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.context.plugin.machine.dictionary_inspection.port import (
    DictionaryInspectionProcessStatePort,
    DictionaryInspectionStateEvaluatorPort,
    DictionaryInspectionStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.dictionary_inspection.state import (
    DictionaryInspectionProcessState,
)


class DictionaryInspectionStateEvaluatorAdapter(
    DictionaryInspectionStateEvaluatorPort
):
    """Evaluate progress from generic dictionary-inspection context outputs."""

    STATE_TO_CAPABILITY_ID: ClassVar[
        Dict[DictionaryInspectionProcessStatePort, str]
    ] = {
        DictionaryInspectionProcessState.TEXT_NORMALIZED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_normalized"
        ),
        DictionaryInspectionProcessState.TEXT_LANGUAGE_IDENTIFIED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_language_identified"
        ),
        DictionaryInspectionProcessState.TEXT_LEMMATIZED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "text_lemmatized"
        ),
        DictionaryInspectionProcessState.ONTOLOGY_TERM_RESOLVED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "ontology_term_resolved"
        ),
        DictionaryInspectionProcessState.KIND_REPRESENTATION_RESOLVED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "kind_representation_resolved"
        ),
        DictionaryInspectionProcessState.MARKDOWN_RENDERED: (
            "org.ontobdc.context.plugin.capability.persister.target."
            "dictionary_inspection_markdown_rendered"
        ),
    }

    def evaluate(
        self,
        context: CliContextPort,
    ) -> DictionaryInspectionProcessStatePort:
        reached_state: DictionaryInspectionProcessStatePort = (
            DictionaryInspectionProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self._state_sequence()[1:]:
            state: DictionaryInspectionProcessStatePort = (
                DictionaryInspectionProcessState.get_state(state_name)
            )
            if not self._capability_for(state).is_satisfied(context):
                return reached_state
            reached_state = state
        return reached_state

    @classmethod
    def _state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(cls._statechart_data())

    @staticmethod
    def _statechart_data() -> Dict[str, Any]:
        statechart_file_path: Path = StatechartLocator.locate(
            "ontobdc.context.plugin.machine.dictionary_inspection",
            "standard_dictionary_inspection.yaml",
        )
        return yaml.safe_load(statechart_file_path.read_text(encoding="utf-8"))

    @classmethod
    def _capability_for(
        cls,
        state: DictionaryInspectionProcessStatePort,
    ) -> CapabilityPort:
        if state not in cls.STATE_TO_CAPABILITY_ID:
            raise ValueError(
                "Dictionary inspection capability identifier not available for "
                f"state: {state.value}"
            )
        capability_id: str = cls.STATE_TO_CAPABILITY_ID[state]
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Dictionary inspection capability not found: {capability_id}"
            )
        return capability_type()


class DictionaryInspectionStateTransitionHandler(
    DictionaryInspectionStateTransitionHandlerPort
):
    TEXT_KEY: ClassVar[str] = "text"
    MARKDOWN_KEY: ClassVar[str] = "result_markdown"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DictionaryInspectionStateEvaluatorPort = (
            DictionaryInspectionStateEvaluatorAdapter()
        )
        self._active_state: Optional[DictionaryInspectionProcessStatePort] = None
        self._observed_state: Optional[DictionaryInspectionProcessStatePort] = None

    @property
    def current_state(self) -> DictionaryInspectionProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> DictionaryInspectionProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> None:
        observed_state: DictionaryInspectionProcessStatePort = self.observed_state
        if self._state_reaches(observed_state, to_state):
            return

        self._logger.log_info(
            "Dictionary inspection transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = (
            DictionaryInspectionStateEvaluatorAdapter._capability_for(to_state)
        )
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: DictionaryInspectionProcessStatePort,
        to_state: DictionaryInspectionProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DictionaryInspectionProcessState,
            state_context_name="DictionaryInspectionProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        worker.work()
        if self.current_state != DictionaryInspectionProcessState.MARKDOWN_RENDERED:
            raise RuntimeError(
                "Dictionary inspection stopped at state "
                f"'{self.current_state.value}' instead of "
                f"'{DictionaryInspectionProcessState.MARKDOWN_RENDERED.value}'."
            )
        return CommandResponse(
            title="Context Dictionary Inspect",
            description=(
                "Dictionary inspection of "
                f"'{RequiredParameter.of(self._context, self.TEXT_KEY)}'."
            ),
            content=RequiredParameter.of(self._context, self.MARKDOWN_KEY),
        )

    @staticmethod
    def _get_statechart_file_path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.context.plugin.machine.dictionary_inspection",
            "standard_dictionary_inspection.yaml",
        )

    def bind_active_state(
        self,
        state: DictionaryInspectionProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    @staticmethod
    def _state_reaches(
        observed_state: DictionaryInspectionProcessStatePort,
        target_state: DictionaryInspectionProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = (
            DictionaryInspectionStateEvaluatorAdapter._state_sequence()
        )
        observed_name: str = observed_state.name.lower()
        target_name: str = target_state.name.lower()
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the statechart."
            )
        return state_sequence.index(observed_name) >= state_sequence.index(
            target_name
        )

    def _forget_observed_state(self) -> None:
        self._observed_state = None
