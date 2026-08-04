import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.context.adapter.repository import EntityAnalysisStepRepository, EntityLearningStepRepository
from ontobdc.context.domain.machine.learning_state import EntityAnalysisProcessState, EntityLearningProcessState
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort


class EntityLearningStateTransitionHandler:
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._active_state: Optional[EntityLearningProcessState] = None
        self._step_repository: EntityLearningStepRepository = context.get_parameter_value("step_repository")
        self._target_path: Path = self._step_repository.source_path

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> EntityLearningProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> EntityLearningProcessState:
        for state in [
            EntityLearningProcessState.PUBLISHED,
            EntityLearningProcessState.ALIGNED,
            EntityLearningProcessState.SPATIALIZED,
            EntityLearningProcessState.EXTRACTED,
            EntityLearningProcessState.IDENTIFIED,
        ]:
            if self._step_repository.exists(state):
                return state
        return EntityLearningProcessState.UNDEFINED

    @property
    def state_sequence(self) -> List[EntityLearningProcessState]:
        return list(EntityLearningProcessState)

    def can_transit_to(self, to_state: EntityLearningProcessState) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: EntityLearningProcessState) -> None:
        if self.observed_state == to_state:
            return

        capability_id: str = (
            f"org.ontobdc.context.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Context learning capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: EntityLearningProcessState,
        to_state: EntityLearningProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        return self.observed_state == to_state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=EntityLearningProcessState,
            state_context_name="EntityLearningProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        worker.work()
        visited_states: List[str] = self._materialized_states()
        return self._build_final_response(visited_states)

    def bind_active_state(self, state: EntityLearningProcessState) -> None:
        self._active_state = state

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state != EntityLearningProcessState.PUBLISHED:
            return ExceptionCommandResponse(
                title="Context Learning Incomplete",
                description="The entity learning pipeline did not reach the published state.",
                content={
                    "source_path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                    "step_dir": str(self._step_repository.step_dir),
                },
            )

        published_resource = self._step_repository.reload(EntityLearningProcessState.PUBLISHED)
        published_content: Any = published_resource.content
        if isinstance(published_content, bytes):
            published_content = published_content.decode("utf-8")
        payload: Dict[str, Any] = json.loads(str(published_content))

        return CommandResponse(
            title="Context Entity Learned",
            description=f"Learned entity profile from '{self._target_path}'.",
            content={
                "source_path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "step_dir": str(self._step_repository.step_dir),
                "published": payload,
            },
        )

    def _materialized_states(self) -> List[str]:
        materialized_states: List[str] = [EntityLearningProcessState.UNDEFINED.value]
        for state in [
            EntityLearningProcessState.IDENTIFIED,
            EntityLearningProcessState.EXTRACTED,
            EntityLearningProcessState.SPATIALIZED,
            EntityLearningProcessState.ALIGNED,
            EntityLearningProcessState.PUBLISHED,
        ]:
            if self._step_repository.exists(state):
                materialized_states.append(state.value)
        return materialized_states

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_entity_learning.yaml"


class EntityAnalysisStateTransitionHandler:
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._active_state: Optional[EntityAnalysisProcessState] = None
        self._step_repository: EntityAnalysisStepRepository = context.get_parameter_value("step_repository")
        self._target_path: Path = self._step_repository.source_path

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> EntityAnalysisProcessState:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> EntityAnalysisProcessState:
        for state in [
            EntityAnalysisProcessState.ANALYSED,
            EntityAnalysisProcessState.SCORED,
            EntityAnalysisProcessState.VECTORS_LOADED,
            EntityAnalysisProcessState.ORIGIN_RESOLVED,
            EntityAnalysisProcessState.ALIGNED,
            EntityAnalysisProcessState.SPATIALIZED,
            EntityAnalysisProcessState.EXTRACTED,
            EntityAnalysisProcessState.IDENTIFIED,
        ]:
            if self._step_repository.exists(state):
                return state
        return EntityAnalysisProcessState.UNDEFINED

    @property
    def state_sequence(self) -> List[EntityAnalysisProcessState]:
        return list(EntityAnalysisProcessState)

    def can_transit_to(self, to_state: EntityAnalysisProcessState) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: EntityAnalysisProcessState) -> None:
        if self.observed_state == to_state:
            return

        capability_id: str = (
            f"org.ontobdc.context.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Context analysis capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: EntityAnalysisProcessState,
        to_state: EntityAnalysisProcessState,
    ) -> bool:
        if from_state == to_state:
            return False
        return self.observed_state == to_state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=EntityAnalysisProcessState,
            state_context_name="EntityAnalysisProcessState",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        worker.work()
        visited_states: List[str] = self._materialized_states()
        return self._build_final_response(visited_states)

    def bind_active_state(self, state: EntityAnalysisProcessState) -> None:
        self._active_state = state

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state != EntityAnalysisProcessState.ANALYSED:
            return ExceptionCommandResponse(
                title="Context Analysis Incomplete",
                description="The entity analysis pipeline did not reach the analysed state.",
                content={
                    "source_path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                    "step_dir": str(self._step_repository.step_dir),
                },
            )

        analysed_resource = self._step_repository.reload(EntityAnalysisProcessState.ANALYSED)
        analysed_content: Any = analysed_resource.content
        if isinstance(analysed_content, bytes):
            analysed_content = analysed_content.decode("utf-8")
        payload: Dict[str, Any] = json.loads(str(analysed_content))

        return CommandResponse(
            title="Context Entity Analysed",
            description=f"Analysed entity type from '{self._target_path}'.",
            content={
                "source_path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "step_dir": str(self._step_repository.step_dir),
                "analysed": payload,
            },
        )

    def _materialized_states(self) -> List[str]:
        materialized_states: List[str] = [EntityAnalysisProcessState.UNDEFINED.value]
        for state in [
            EntityAnalysisProcessState.IDENTIFIED,
            EntityAnalysisProcessState.EXTRACTED,
            EntityAnalysisProcessState.SPATIALIZED,
            EntityAnalysisProcessState.ALIGNED,
            EntityAnalysisProcessState.ORIGIN_RESOLVED,
            EntityAnalysisProcessState.VECTORS_LOADED,
            EntityAnalysisProcessState.SCORED,
            EntityAnalysisProcessState.ANALYSED,
        ]:
            if self._step_repository.exists(state):
                materialized_states.append(state.value)
        return materialized_states

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_entity_analysis.yaml"
