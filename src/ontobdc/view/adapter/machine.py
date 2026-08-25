from pathlib import Path
from typing import Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.view.domain.machine.state import ContainerViewProcessState
from ontobdc.view.domain.port.machine import (
    ContainerViewProcessStatePort,
    ContainerViewStateEvaluatorPort,
    ContainerViewStateTransitionHandlerPort,
)


_CAPABILITY_ID_BY_STATE: Dict[ContainerViewProcessState, str] = {
    ContainerViewProcessState.DATA_GATHERED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "data_gathered"
    ),
    ContainerViewProcessState.HARDCODED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "hardcoded"
    ),
    ContainerViewProcessState.FACADES_SERIALIZED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "facades_serialized"
    ),
    ContainerViewProcessState.DATASET_VIEWS_GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "dataset_views_generated"
    ),
    ContainerViewProcessState.GENERATED: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "generated"
    ),
}


def _capability_type_for_state(
    state: ContainerViewProcessStatePort,
) -> Type[CapabilityPort]:
    try:
        capability_id = _CAPABILITY_ID_BY_STATE[
            ContainerViewProcessState(state)
        ]
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"No transformation capability is mapped to legacy view state: {state}"
        ) from exc

    capability_type = CapabilityLoader().get(capability_id)
    if capability_type is None:
        raise ValueError(
            f"Legacy container view capability not found: {capability_id}"
        )
    return capability_type


class ContainerViewStateEvaluatorAdapter(ContainerViewStateEvaluatorPort):
    """Infer the latest satisfied legacy view state from executable capabilities."""

    @property
    def process_state_class(self) -> Type[ContainerViewProcessStatePort]:
        return ContainerViewProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerViewProcessStatePort:
        for state in reversed(self.state_sequence):
            if state == ContainerViewProcessState.UNDEFINED:
                continue

            capability_type = _capability_type_for_state(state)
            capability = capability_type()
            is_satisfied = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied):
                raise TypeError(
                    "Legacy container view state capability does not implement "
                    f"is_satisfied(context): {capability_type.__name__}"
                )
            if bool(is_satisfied(context)):
                return state

        return ContainerViewProcessState.UNDEFINED

    @property
    def state_sequence(self) -> List[ContainerViewProcessStatePort]:
        return list(ContainerViewProcessState)


class ContainerViewStateTransitionHandler(
    ContainerViewStateTransitionHandlerPort
):
    """Execute the remaining legacy view transformations after publication prerequisites."""

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[ContainerViewStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._target_path = Path(
            str(self._context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        self._state_evaluator = (
            state_evaluator or ContainerViewStateEvaluatorAdapter()
        )
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[ContainerViewProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ContainerViewProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> ContainerViewProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ContainerViewProcessStatePort]:
        return list(ContainerViewProcessState)

    def can_transit_to(
        self,
        to_state: ContainerViewProcessStatePort,
    ) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: ContainerViewProcessStatePort,
    ) -> None:
        self._logger.log_info(
            f"Legacy container view target state: {to_state.value}",
        )
        capability_type = _capability_type_for_state(to_state)
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: ContainerViewProcessStatePort,
        to_state: ContainerViewProcessStatePort,
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

    def execute(self) -> CommandResponse:
        worker = StateWorkerAdapter(
            state_adapter=ContainerViewProcessState,
            state_context_name="ContainerViewProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states = worker.work()
        return CommandResponse(
            title="Container View Generated",
            description=(
                "The legacy container view process reached its generated state."
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
            "standard_container_view.yaml",
        )

    def bind_active_state(
        self,
        state: ContainerViewProcessStatePort,
    ) -> None:
        self._active_state = state
