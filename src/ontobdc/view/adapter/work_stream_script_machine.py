from pathlib import Path
from typing import Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.view.adapter.surface.transformation import SurfaceTransformationAdapter
from ontobdc.view.domain.machine.work_stream_script_state import (
    WorkStreamScriptGenerationProcessState,
)
from ontobdc.view.domain.port.work_stream_script_machine import (
    WorkStreamScriptGenerationProcessStatePort,
    WorkStreamScriptGenerationStateEvaluatorPort,
    WorkStreamScriptGenerationStateTransitionHandlerPort,
)


_CAPABILITY_ID_BY_STATE: Dict[WorkStreamScriptGenerationProcessState, str] = {
    WorkStreamScriptGenerationProcessState.I18N_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_i18n_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.GRAPH_READER_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_graph_reader_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.CSV_PREVIEW_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_csv_preview_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.CONTAINER_CONNECTION_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_container_connection_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.CONNECTION_STATE_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_connection_state_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.ANNOTATION_BRIDGE_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_annotation_bridge_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.PYODIDE_RUNTIME_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_pyodide_runtime_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.LINKSET_OPERATIONS_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_linkset_operations_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.FILE_CATEGORY_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_file_category_script_generated"
    ),
    WorkStreamScriptGenerationProcessState.DIMENSION_CARD_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "work_stream_dimension_card_script_generated"
    ),
}


def _capability_type_for_state(
    state: WorkStreamScriptGenerationProcessStatePort,
) -> Type[CapabilityPort]:
    try:
        capability_id = _CAPABILITY_ID_BY_STATE[
            WorkStreamScriptGenerationProcessState(state)
        ]
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"No transformation capability is mapped to work_stream_view "
            f"script generation state: {state}"
        ) from exc

    capability_type = CapabilityLoader().get(capability_id)
    if capability_type is None:
        raise ValueError(
            f"work_stream_view script generation capability not found: {capability_id}"
        )
    return capability_type


class WorkStreamScriptGenerationStateEvaluatorAdapter(
    WorkStreamScriptGenerationStateEvaluatorPort
):
    """Infer the latest satisfied work_stream_view script generation state
    from the corresponding transformation capabilities' `is_satisfied`."""

    @property
    def process_state_class(self) -> Type[WorkStreamScriptGenerationProcessStatePort]:
        return WorkStreamScriptGenerationProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> WorkStreamScriptGenerationProcessStatePort:
        for state in reversed(self.state_sequence):
            if state == WorkStreamScriptGenerationProcessState.UNDEFINED:
                continue

            capability_type = _capability_type_for_state(state)
            capability = capability_type()
            is_satisfied = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied):
                raise TypeError(
                    "work_stream_view script generation state capability does "
                    f"not implement is_satisfied(context): {capability_type.__name__}"
                )
            if bool(is_satisfied(context)):
                return state

        return WorkStreamScriptGenerationProcessState.UNDEFINED

    @property
    def state_sequence(self) -> List[WorkStreamScriptGenerationProcessStatePort]:
        return list(WorkStreamScriptGenerationProcessState)


class WorkStreamScriptGenerationStateTransitionHandler(
    WorkStreamScriptGenerationStateTransitionHandlerPort
):
    """Execute the remaining work_stream_view script generation states, one
    generated JS file per state, in the container that hosts `index.html`.
    """

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[WorkStreamScriptGenerationStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._surface = SurfaceTransformationAdapter()
        self._target_path = self._surface.path(context).parent
        self._state_evaluator = (
            state_evaluator or WorkStreamScriptGenerationStateEvaluatorAdapter()
        )
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[WorkStreamScriptGenerationProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> WorkStreamScriptGenerationProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> WorkStreamScriptGenerationProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[WorkStreamScriptGenerationProcessStatePort]:
        return list(WorkStreamScriptGenerationProcessState)

    def can_transit_to(
        self,
        to_state: WorkStreamScriptGenerationProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: WorkStreamScriptGenerationProcessStatePort,
    ) -> None:
        self._logger.log_info(
            f"work_stream_view script generation target state: {to_state.value}",
        )
        capability_type = _capability_type_for_state(to_state)
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: WorkStreamScriptGenerationProcessStatePort,
        to_state: WorkStreamScriptGenerationProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        observed_state = self.observed_state
        if observed_state == to_state:
            return True

        state_sequence = self.state_sequence
        if (
            to_state not in state_sequence
            or observed_state not in state_sequence
        ):
            return False

        return (
            state_sequence.index(observed_state)
            > state_sequence.index(to_state)
        )

    def execute(self):
        from ontobdc.cli.domain.response.command import CommandResponse

        worker = StateWorkerAdapter(
            state_adapter=WorkStreamScriptGenerationProcessState,
            state_context_name="WorkStreamScriptGenerationProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states = worker.work()
        return CommandResponse(
            title="WorkStream View Scripts Generated",
            description=(
                "The work_stream_view script generation process reached its "
                "final state."
            ),
            content={
                "container_path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _get_statechart_file_path(self) -> Path:
        return StatechartLocator.locate(
            __file__,
            "standard_work_stream_script_generation.yaml",
        )

    def bind_active_state(
        self,
        state: WorkStreamScriptGenerationProcessStatePort,
    ) -> None:
        self._active_state = state
