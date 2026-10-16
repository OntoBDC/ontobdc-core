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
from ontobdc.context.plugin.machine.entity_inspection.port import (
    EntityInspectionProcessStatePort,
    EntityInspectionStateEvaluatorPort,
    EntityInspectionStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.entity_inspection.state import (
    EntityInspectionProcessState,
)


class EntityInspectionStateEvaluatorAdapter(
    EntityInspectionStateEvaluatorPort
):
    """Evaluate whether the requested entity's information was found."""

    STATE_TO_CAPABILITY_ID: ClassVar[
        Dict[EntityInspectionProcessStatePort, str]
    ] = {
        EntityInspectionProcessState.ENTITY_URI_RESOLVED: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "entity_uri_resolved"
        ),
        EntityInspectionProcessState.ENTITY_INFORMATION_FOUND: (
            "org.ontobdc.context.plugin.capability.transformation.target."
            "entity_information_found"
        ),
    }

    def evaluate(
        self,
        context: CliContextPort,
    ) -> EntityInspectionProcessStatePort:
        reached_state: EntityInspectionProcessStatePort = (
            EntityInspectionProcessState.UNDEFINED
        )
        state_name: str
        for state_name in self._state_sequence()[1:]:
            state: EntityInspectionProcessStatePort = (
                EntityInspectionProcessState.get_state(state_name)
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
            "ontobdc.context.plugin.machine.entity_inspection",
            "standard_entity_inspection.yaml",
        )
        return yaml.safe_load(statechart_file_path.read_text(encoding="utf-8"))

    @classmethod
    def _capability_for(
        cls,
        state: EntityInspectionProcessStatePort,
    ) -> CapabilityPort:
        if state not in cls.STATE_TO_CAPABILITY_ID:
            raise ValueError(
                "Entity inspection capability identifier not available for "
                f"state: {state.value}"
            )
        capability_id: str = cls.STATE_TO_CAPABILITY_ID[state]
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Entity inspection capability not found: {capability_id}"
            )
        return capability_type()


class EntityInspectionStateTransitionHandler(
    EntityInspectionStateTransitionHandlerPort
):
    ENTITY_KEY: ClassVar[str] = "entity_id"
    INFORMATION_KEY: ClassVar[str] = "entity_information"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: EntityInspectionStateEvaluatorPort = (
            EntityInspectionStateEvaluatorAdapter()
        )
        self._active_state: Optional[EntityInspectionProcessStatePort] = None
        self._observed_state: Optional[EntityInspectionProcessStatePort] = None

    @property
    def current_state(self) -> EntityInspectionProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> EntityInspectionProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(
        self,
        to_state: EntityInspectionProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: EntityInspectionProcessStatePort,
    ) -> None:
        observed_state: EntityInspectionProcessStatePort = self.observed_state
        if self._state_reaches(observed_state, to_state):
            return

        self._logger.log_info(
            "Entity inspection transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = (
            EntityInspectionStateEvaluatorAdapter._capability_for(to_state)
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
        from_state: EntityInspectionProcessStatePort,
        to_state: EntityInspectionProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=EntityInspectionProcessState,
            state_context_name="EntityInspectionProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        worker.work()
        if self.current_state != EntityInspectionProcessState.ENTITY_INFORMATION_FOUND:
            raise RuntimeError(
                "Entity inspection stopped at state "
                f"'{self.current_state.value}' instead of "
                f"'{EntityInspectionProcessState.ENTITY_INFORMATION_FOUND.value}'."
            )
        return CommandResponse(
            title="Context Entity Inspect",
            description=self._description(),
            content=self._context.get_parameter_value(self.INFORMATION_KEY),
        )

    def _description(self) -> str:
        entity_id: Optional[str] = RequiredParameter.optional(self._context, self.ENTITY_KEY)
        if entity_id is None:
            return "Entities published by brasidatacenter."
        return f"Facade of the entity <{entity_id}>."

    @staticmethod
    def _get_statechart_file_path() -> Path:
        return StatechartLocator.locate(
            "ontobdc.context.plugin.machine.entity_inspection",
            "standard_entity_inspection.yaml",
        )

    def bind_active_state(
        self,
        state: EntityInspectionProcessStatePort,
    ) -> None:
        self._active_state = state
        self._forget_observed_state()

    @staticmethod
    def _state_reaches(
        observed_state: EntityInspectionProcessStatePort,
        target_state: EntityInspectionProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = (
            EntityInspectionStateEvaluatorAdapter._state_sequence()
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
