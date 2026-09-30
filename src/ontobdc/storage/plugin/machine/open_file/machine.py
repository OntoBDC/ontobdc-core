from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, cast

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.loader import RootPackagesAwarePort
from ontobdc.storage.plugin.machine.open_file.port import (
    OpenFileProcessStatePort,
    OpenFileStateEvaluatorPort,
    OpenFileStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.machine.open_file.state import OpenFileProcessState
from ontobdc.storage.plugin.machine.open_file.statechart import OpenFileStatechart


def _load_state_capability(
    loader: CapabilityLoader,
    root_packages: Tuple[str, ...],
    state: OpenFileProcessStatePort,
) -> CapabilityPort:
    capability_id = OpenFileStatechart.capability_id(state)
    capability_type = loader.get(capability_id)
    if capability_type is None:
        raise ValueError(f"Open-file capability not found: {capability_id}")

    capability: CapabilityPort = capability_type()
    if isinstance(capability, RootPackagesAwarePort):
        capability.set_root_packages(root_packages)
    return capability


class OpenFileStateEvaluatorAdapter(OpenFileStateEvaluatorPort):
    """Read durable open-file states from their capability contracts."""

    def __init__(self, root_packages: Tuple[str, ...]) -> None:
        self._root_packages = root_packages
        self._loader = CapabilityLoader(root_packages=root_packages)

    def evaluate(self, context: CliContextPort) -> OpenFileProcessStatePort:
        reached_state: OpenFileProcessStatePort = OpenFileProcessState.UNDEFINED

        for state_name in OpenFileStatechart.sequence()[1:]:
            state = OpenFileProcessState.get_state(state_name)

            # Opening is an action, not persistent readiness. Every invocation
            # must execute the terminal strategy state again.
            if OpenFileStatechart.is_terminal(state):
                return reached_state

            capability = _load_state_capability(
                self._loader,
                self._root_packages,
                state,
            )
            is_satisfied = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied) or not is_satisfied(context):
                return reached_state

            reached_state = state

        return reached_state


class OpenFileStateTransitionHandler(OpenFileStateTransitionHandlerPort):
    """Execute transitions declared by the open-file statechart."""

    def __init__(
        self,
        context: CliContextPort,
        root_packages: Tuple[str, ...] = ("ontobdc",),
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context = context
        self._root_packages = root_packages
        self._logger = logger or NullLogRepository()
        self._loader = CapabilityLoader(root_packages=root_packages)
        self._resolver = StrategyParamResolver(
            ResolverLoader(root_packages=root_packages)
        )
        self._state_evaluator: OpenFileStateEvaluatorPort = (
            OpenFileStateEvaluatorAdapter(root_packages)
        )
        self._active_state: Optional[OpenFileProcessStatePort] = None
        self._observed_state: Optional[OpenFileProcessStatePort] = None
        self._last_performed_state: Optional[OpenFileProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> OpenFileProcessStatePort:
        if self._active_state is not None:
            return self._active_state
        return self.observed_state

    @property
    def observed_state(self) -> OpenFileProcessStatePort:
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)
        return self._observed_state

    def can_transit_to(self, to_state: OpenFileProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(
        self,
        to_state: OpenFileProcessStatePort,
    ) -> None:
        if (
            not OpenFileStatechart.is_terminal(to_state)
            and self.observed_state == to_state
        ):
            return

        capability = _load_state_capability(
            self._loader,
            self._root_packages,
            to_state,
        )
        self._logger.log_info(
            "Open-file transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )

        try:
            self._result = CapabilityExecutor.execute(
                capability,
                self._context,
                self._resolver,
            )
            self._last_performed_state = to_state
        finally:
            self._forget_observed_state()

    def validate_state_transition(
        self,
        from_state: OpenFileProcessStatePort,
        to_state: OpenFileProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        if OpenFileStatechart.is_terminal(to_state):
            return self._last_performed_state == to_state

        sequence = OpenFileStatechart.sequence()
        observed_name = self.observed_state.value.strip("_")
        target_name = to_state.value.strip("_")
        if observed_name not in sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "open-file statechart."
            )
        if target_name not in sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the "
                "open-file statechart."
            )

        return sequence.index(observed_name) >= sequence.index(target_name)

    def execute(self) -> Dict[str, Dict[str, Any]]:
        worker = StateWorkerAdapter(
            state_adapter=OpenFileProcessState,
            state_context_name="OpenFileProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=OpenFileStatechart.path(),
        )
        worker.work()
        return cast(Dict[str, Dict[str, Any]], dict(self._result))

    def bind_active_state(self, state: OpenFileProcessStatePort) -> None:
        self._active_state = state
        self._forget_observed_state()

    def _forget_observed_state(self) -> None:
        self._observed_state = None


class OpenFileMachine:
    """Run the open-file FSM."""

    def __init__(
        self,
        context: CliContextPort,
        root_packages: Tuple[str, ...] = ("ontobdc",),
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._handler = OpenFileStateTransitionHandler(
            context=context,
            root_packages=root_packages,
            logger=logger,
        )

    def work(self) -> Dict[str, Dict[str, Any]]:
        return self._handler.execute()
