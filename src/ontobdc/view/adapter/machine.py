from pathlib import Path
from typing import List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
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


class ContainerViewStateEvaluatorAdapter(ContainerViewStateEvaluatorPort):
    """Infer the current state from the artefacts produced by the process."""

    @property
    def process_state_class(self) -> Type[ContainerViewProcessStatePort]:
        return ContainerViewProcessState

    def evaluate(self, context: CliContextPort) -> ContainerViewProcessStatePort:
        if self._generated_check(context):
            return ContainerViewProcessState.GENERATED
        if self._data_gathered_check(context):
            return ContainerViewProcessState.DATA_GATHERED
        if self._is_publishable_check(context):
            return ContainerViewProcessState.IS_PUBLISHABLE
        if self._container_healthy_check(context):
            return ContainerViewProcessState.CONTAINER_HEALTHY
        return ContainerViewProcessState.UNDEFINED


class ContainerViewStateTransitionHandler(ContainerViewStateTransitionHandlerPort):
    """Execute the transformation that knows how to produce the requested target state."""

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: ContainerViewStateEvaluatorPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._target_path = Path(
            self._context.get_parameter_value("container_path")
        ).expanduser().resolve()
        self._state_evaluator = state_evaluator
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

    def can_transit_to(self, to_state: ContainerViewProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: ContainerViewProcessStatePort) -> None:
        self._logger.log_info(
            f"Container view target state: {to_state.value}",
        )

        capability_type = self._get_target_state_capability(to_state)
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
        if to_state not in state_sequence or observed_state not in state_sequence:
            return False

        return state_sequence.index(observed_state) > state_sequence.index(to_state)

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
            description="The container view process reached its generated state.",
            content={
                "container_path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _get_target_state_capability(
        self,
        to_state: ContainerViewProcessStatePort,
    ) -> Type[CapabilityPort]:
        target_suffix = (
            ".plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        matches = []

        for capability_type in CapabilityLoader().get_all():
            metadata = getattr(capability_type, "METADATA", None)
            capability_id = getattr(metadata, "id", "")
            if isinstance(capability_id, str) and capability_id.endswith(target_suffix):
                matches.append(capability_type)

        if not matches:
            raise ValueError(
                "Transformation capability not found for target state: "
                f"{to_state.value}"
            )

        if len(matches) > 1:
            capability_ids = sorted(
                getattr(getattr(item, "METADATA", None), "id", "")
                for item in matches
            )
            raise ValueError(
                "Multiple transformation capabilities found for target state "
                f"{to_state.value}: {capability_ids}"
            )

        return matches[0]

    def _get_statechart_file_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "domain"
            / "machine"
            / "standard_container_view.yaml"
        )

    def bind_active_state(self, state: ContainerViewProcessStatePort) -> None:
        self._active_state = state
