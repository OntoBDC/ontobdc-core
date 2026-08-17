from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
from ontobdc.view.domain.machine.surface_state import SurfaceGenerationProcessState
from ontobdc.view.domain.port.surface_machine import (
    SurfaceGenerationProcessStatePort,
    SurfaceGenerationStateEvaluatorPort,
    SurfaceGenerationStateTransitionHandlerPort,
)


_CAPABILITY_ID_BY_STATE: Dict[SurfaceGenerationProcessState, str] = {
    SurfaceGenerationProcessState.CONTAINER_HEALTHY: (
        "org.ontobdc.storage.plugin.capability.transformation.target."
        "container_healthy"
    ),
    SurfaceGenerationProcessState.IS_PUBLISHABLE: (
        "org.ontobdc.view.plugin.capability.transformation.target."
        "is_publishable"
    ),
    **{
        state: (
            "org.ontobdc.view.plugin.capability.transformation.target."
            f"{state.value.strip('_')}"
        )
        for state in SurfaceGenerationProcessState
        if state
        not in {
            SurfaceGenerationProcessState.UNDEFINED,
            SurfaceGenerationProcessState.CONTAINER_HEALTHY,
            SurfaceGenerationProcessState.IS_PUBLISHABLE,
        }
    },
}


def _capability_type_for_state(state: SurfaceGenerationProcessStatePort) -> Type[CapabilityPort]:
    normalized = SurfaceGenerationProcessState(state)
    capability_id = _CAPABILITY_ID_BY_STATE.get(normalized)
    if not capability_id:
        raise ValueError(f"No transformation capability is mapped to Surface state: {state}")
    capability_type: Any = CapabilityLoader().get(capability_id)
    if capability_type is None:
        raise ValueError(f"Surface generation capability not found: {capability_id}")
    return capability_type


class SurfaceGenerationStateEvaluatorAdapter(SurfaceGenerationStateEvaluatorPort):
    """Infer the latest cumulatively satisfied Surface-generation state."""

    @property
    def process_state_class(self) -> Type[SurfaceGenerationProcessStatePort]:
        return SurfaceGenerationProcessState

    @property
    def state_sequence(self) -> List[SurfaceGenerationProcessStatePort]:
        return list(SurfaceGenerationProcessState)

    def evaluate(self, context: CliContextPort) -> SurfaceGenerationProcessStatePort:
        latest: SurfaceGenerationProcessStatePort = SurfaceGenerationProcessState.UNDEFINED

        for state in self.state_sequence:
            if state == SurfaceGenerationProcessState.UNDEFINED:
                continue

            if state.value.startswith("__surface_"):
                try:
                    SurfaceContextAdapter().surface_path(context)
                except ValueError:
                    break

            capability_type = _capability_type_for_state(state)
            capability = capability_type()
            check = getattr(capability, "check", None)
            if not callable(check):
                raise TypeError(
                    "Surface transformation capability does not implement "
                    f"check(context): {capability_type.__name__}"
                )
            if not bool(check(context)):
                break

            latest = state

        return latest


class SurfaceGenerationStateTransitionHandler(SurfaceGenerationStateTransitionHandlerPort):
    """Drive container prerequisites and cumulative offline HTML Surface transformations."""

    def __init__(
        self,
        context: CliContextPort,
        state_evaluator: Optional[SurfaceGenerationStateEvaluatorPort] = None,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._state_evaluator = state_evaluator or SurfaceGenerationStateEvaluatorAdapter()
        self._logger = logger or NullLogRepository()
        self._active_state: Optional[SurfaceGenerationProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return SurfaceContextAdapter().surface_path(self._context)

    @property
    def observed_state(self) -> SurfaceGenerationProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def current_state(self) -> SurfaceGenerationProcessStatePort:
        return self._active_state if self._active_state is not None else self.observed_state

    @property
    def state_sequence(self) -> List[SurfaceGenerationProcessStatePort]:
        return list(SurfaceGenerationProcessState)

    def can_transit_to(self, to_state: SurfaceGenerationProcessStatePort) -> bool:
        sequence = self.state_sequence
        current = self.current_state
        if current not in sequence or to_state not in sequence:
            return False
        current_index = sequence.index(current)
        return current_index + 1 < len(sequence) and sequence[current_index + 1] == to_state

    def perform_state_transition(self, to_state: SurfaceGenerationProcessStatePort) -> None:
        self._logger.log_info(
            f"HTML Surface transition: {self.current_state.value} -> {to_state.value}"
        )
        capability_type = _capability_type_for_state(to_state)
        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: SurfaceGenerationProcessStatePort,
        to_state: SurfaceGenerationProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        sequence = self.state_sequence
        observed_state = self.observed_state
        if observed_state not in sequence or to_state not in sequence:
            return False

        # observed_state is cumulative, so overshooting to_state still satisfies it — exact equality would reject that.
        return sequence.index(observed_state) >= sequence.index(to_state)

    def execute_until(
        self,
        stop_state: SurfaceGenerationProcessStatePort,
    ) -> List[str]:
        worker = self._make_worker()
        return worker.work(stop_state=stop_state)

    def execute(self) -> CommandResponse:
        visited_states = self._make_worker().work()
        return CommandResponse(
            title="Presentation Surface Generated",
            description="The offline HTML Presentation Surface reached surface_validated.",
            content={
                "surface_path": str(self.target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _make_worker(self) -> StateWorkerAdapter:
        return StateWorkerAdapter(
            state_adapter=SurfaceGenerationProcessState,
            state_context_name="SurfaceGenerationProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )

    def _get_statechart_file_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent.parent
            / "domain"
            / "machine"
            / "standard_surface_html.yaml"
        )

    def bind_active_state(self, state: SurfaceGenerationProcessStatePort) -> None:
        self._active_state = state
