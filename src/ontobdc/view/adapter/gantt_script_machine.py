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
from ontobdc.view.domain.machine.gantt_script_state import (
    GanttScriptGenerationProcessState,
)
from ontobdc.view.domain.port.gantt_script_machine import (
    GanttScriptGenerationProcessStatePort,
    GanttScriptGenerationStateEvaluatorPort,
    GanttScriptGenerationStateTransitionHandlerPort,
)


_CAPABILITY_ID_BY_STATE: Dict[GanttScriptGenerationProcessState, str] = {
    GanttScriptGenerationProcessState.I18N_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_i18n_script_generated"
    ),
    GanttScriptGenerationProcessState.GRAPH_READER_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_graph_reader_script_generated"
    ),
    GanttScriptGenerationProcessState.CONTAINER_CONNECTION_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_container_connection_script_generated"
    ),
    GanttScriptGenerationProcessState.CONNECTION_STATE_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_connection_state_script_generated"
    ),
    GanttScriptGenerationProcessState.PYODIDE_RUNTIME_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_pyodide_runtime_script_generated"
    ),
    GanttScriptGenerationProcessState.TASK_TABLE_TIMELINE_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_task_table_timeline_script_generated"
    ),
    GanttScriptGenerationProcessState.DEPENDENCY_ARROWS_SCRIPT_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "gantt_dependency_arrows_script_generated"
    ),
}


def _capability_type_for_state(
    state: GanttScriptGenerationProcessStatePort,
) -> Type[CapabilityPort]:
    try:
        capability_id = _CAPABILITY_ID_BY_STATE[
            GanttScriptGenerationProcessState(state)
        ]
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"No transformation capability is mapped to gantt_view "
            f"script generation state: {state}"
        ) from exc

    capability_type = CapabilityLoader().get(capability_id)
    if capability_type is None:
        raise ValueError(
            f"gantt_view script generation capability not found: {capability_id}"
        )
    return capability_type


class GanttScriptGenerationStateEvaluatorAdapter(
    GanttScriptGenerationStateEvaluatorPort
):
    """Infer the latest satisfied gantt_view script generation state
    from the corresponding transformation capabilities' `is_satisfied`."""

    @property
    def process_state_class(self) -> Type[GanttScriptGenerationProcessStatePort]:
        return GanttScriptGenerationProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> GanttScriptGenerationProcessStatePort:
        for state in reversed(self.state_sequence):
            if state == GanttScriptGenerationProcessState.UNDEFINED:
                continue

            capability_type = _capability_type_for_state(state)
            capability = capability_type()
            is_satisfied = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied):
                raise TypeError(
                    "gantt_view script generation state capability does "
                    f"not implement is_satisfied(context): {capability_type.__name__}"
                )
            if bool(is_satisfied(context)):
                return state

        return GanttScriptGenerationProcessState.UNDEFINED

    @property
    def state_sequence(self) -> List[GanttScriptGenerationProcessStatePort]:
        return list(GanttScriptGenerationProcessState)


class GanttScriptGenerationStateTransitionHandler(
    GanttScriptGenerationStateTransitionHandlerPort
):
    """Execute the remaining gantt_view script generation states, one
    generated JS file per state, in the container that hosts `index.html`.
    """

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[GanttScriptGenerationStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._surface = SurfaceTransformationAdapter()
        self._target_path = self._surface.path(context).parent
        self._state_evaluator = (
            state_evaluator or GanttScriptGenerationStateEvaluatorAdapter()
        )
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[GanttScriptGenerationProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> GanttScriptGenerationProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> GanttScriptGenerationProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[GanttScriptGenerationProcessStatePort]:
        return list(GanttScriptGenerationProcessState)

    def can_transit_to(
        self,
        to_state: GanttScriptGenerationProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: GanttScriptGenerationProcessStatePort,
    ) -> None:
        self._logger.log_info(
            f"gantt_view script generation target state: {to_state.value}",
        )
        capability_type = _capability_type_for_state(to_state)
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: GanttScriptGenerationProcessStatePort,
        to_state: GanttScriptGenerationProcessStatePort,
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
            state_adapter=GanttScriptGenerationProcessState,
            state_context_name="GanttScriptGenerationProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states = worker.work()
        return CommandResponse(
            title="Gantt View Scripts Generated",
            description=(
                "The ifc_work_schedule_view script generation process reached its "
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
            "standard_gantt_script_generation.yaml",
        )

    def bind_active_state(
        self,
        state: GanttScriptGenerationProcessStatePort,
    ) -> None:
        self._active_state = state
