from __future__ import annotations

from typing import Any, Callable, ClassVar, List, Optional
from pathlib import Path
import importlib

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import (
    CapabilityLoader,
    ResolverLoader,
)
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateProcessStatePort,
    ContainerCreateStateEvaluatorPort,
    ContainerCreateStateTransitionHandlerPort,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.container.plugin.machine.container_create.state import (
    ContainerCreateProcessState,
)
from ontobdc.container.plugin.machine.container_create.statechart import (
    ContainerCreateStatechart,
)


class ContainerCreateStateEvaluatorAdapter(ContainerCreateStateEvaluatorPort):
    """
    Reads the container on disk and reports the state it is already in.

    State order comes directly from the statechart YAML. Every observable
    state resolves its standalone check by the mandatory
    ``is_<state>.check.main`` plugin convention.
    """

    CHECK_MODULE_PREFIX: ClassVar[str] = "ontobdc.container.plugin.check.is_"

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerCreateProcessStatePort:
        """
        Return the state the target container directory is already in.
        """
        target_path: Path = (
            Path(context.get_parameter_value("container_path")).expanduser().resolve()
        )
        root_path: Path = Path(context.root_path).expanduser().resolve()

        if not target_path.exists():
            return ContainerCreateProcessState.UNDEFINED

        if not target_path.is_dir():
            return ContainerCreateProcessState.INVALID_PATH

        reached_state: ContainerCreateProcessStatePort = (
            ContainerCreateProcessState.DIRECTORY_READY
        )
        state_name: str
        for state_name in ContainerCreateStatechart.sequence()[1:]:
            state: ContainerCreateProcessStatePort = (
                ContainerCreateProcessState.get_state(state_name)
            )
            check: Callable[..., int] = self._check_for(state)
            if (
                check(
                    root_path=str(root_path),
                    container_path=str(target_path),
                )
                != 0
            ):
                return reached_state

            reached_state = state

        return reached_state

    @classmethod
    def _check_for(
        cls,
        state: ContainerCreateProcessStatePort,
    ) -> Callable[..., int]:
        state_name: str = state.value.strip("_")
        module_name: str = f"{cls.CHECK_MODULE_PREFIX}{state_name}.check"
        check_module: Any = importlib.import_module(module_name)
        check: Any = getattr(check_module, "main")
        if not callable(check):
            raise TypeError(
                f"Container state check is not callable: {module_name}.main"
            )

        return check


class ContainerCreateStateTransitionHandler(ContainerCreateStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = (
            Path(self._context.get_parameter_value("container_path"))
            .expanduser()
            .resolve()
        )
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ContainerCreateStateEvaluatorPort = (
            ContainerCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[ContainerCreateProcessStatePort] = None
        self._observed_state: Optional[ContainerCreateProcessStatePort] = None

    @property
    def current_state(self) -> ContainerCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ContainerCreateProcessStatePort:
        """
        The state the container is in on disk, read once per machine step.

        Evaluating parses the container and the storage index, and every
        guard, action and contract of a step reads this, so the reading is
        held until something can have changed it: a capability that ran, or
        the machine moving to another state.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def _forget_observed_state(self) -> None:
        """
        Drop the reading, so the next one goes back to disk.
        """
        self._observed_state = None

    def can_transit_to(self, to_state: ContainerCreateProcessStatePort) -> bool:
        active_state: ContainerCreateProcessStatePort = self.current_state
        if active_state == ContainerCreateProcessState.UNDEFINED:
            expected_state: ContainerCreateProcessStatePort = (
                ContainerCreateProcessState.INVALID_PATH
                if self.observed_state == ContainerCreateProcessState.INVALID_PATH
                else ContainerCreateProcessState.DIRECTORY_READY
            )
            return to_state == expected_state

        return active_state != to_state

    def perform_state_transition(
        self, to_state: ContainerCreateProcessStatePort
    ) -> None:
        observed_state: ContainerCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"Storage container create transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"org.ontobdc.container.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Storage container create capability not found: {capability_id}"
            )

        capability: CapabilityPort = capability_type()
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
        from_state: ContainerCreateProcessStatePort,
        to_state: ContainerCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        state_sequence: List[str] = ContainerCreateStatechart.sequence()
        observed_state: ContainerCreateProcessStatePort = self.observed_state
        observed_name: str = observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "container create statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the container "
                "create statechart."
            )

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ContainerCreateProcessState,
            state_context_name="ContainerCreateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=ContainerCreateStatechart.path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == ContainerCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid Storage Container Path",
                description="The target path points to an existing file and cannot become a container directory.",
                content={
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="Storage Container Created",
            description="The local storage container directory, metadata, storage index entry, and manifest are ready for the next creation steps.",
            content={
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )

    def bind_active_state(self, state: ContainerCreateProcessStatePort) -> None:
        self._active_state = state
