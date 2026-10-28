from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, List, Optional

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.ddock.adapter.system_descriptor import SystemDescriptors
from ontobdc.ddock.adapter.system_lock import SystemLock
from ontobdc.ddock.domain.model.system_descriptor import SystemDescriptor
from ontobdc.ddock.plugin.machine.system_install.machine import (
    SystemInstallRequest,
)
from ontobdc.ddock.plugin.machine.system_update.port import (
    SystemUpdateProcessStatePort,
    SystemUpdateStateEvaluatorPort,
    SystemUpdateStateTransitionHandlerPort,
)
from ontobdc.ddock.plugin.machine.system_update.state import (
    SystemUpdateProcessState,
)
from ontobdc.ddock.plugin.machine.system_update.statechart import (
    SystemUpdateStatechart,
)


class SystemUpdateRequest(SystemInstallRequest):
    """
    The context keys the update of a system reads and sets, on top of the ones
    the installation uses.

    The update downloads into the same work folder of the container, and runs
    the same steps for the last of them -- the validation of the descriptor,
    the writing of the lock and the build of the node -- so that those steps
    are the same either way. What it adds are the keys that say which of its
    own steps, the refreshing of the ddock and of the packages, have run.
    """

    DDOCK_REFRESHED_KEY: str = "ddock_update_ddock_refreshed"
    PACKAGES_REFRESHED_KEY: str = "ddock_update_packages_refreshed"

    @classmethod
    def ddock_refreshed(cls, context: CliContextPort) -> bool:
        """
        Whether this run already replaced the source folder with the ddock of
        the repository of system.obdc.
        """
        return context.get_parameter_value(cls.DDOCK_REFRESHED_KEY) is True

    @classmethod
    def packages_refreshed(cls, context: CliContextPort) -> bool:
        """
        Whether this run already put the host of every package into the source
        folder of the container.
        """
        return context.get_parameter_value(cls.PACKAGES_REFRESHED_KEY) is True


class SystemUpdateStateEvaluatorAdapter(SystemUpdateStateEvaluatorPort):
    """
    Reads what is on disk and reports how far the update has got.

    Each state resolves its own capability and asks whether it already
    considers itself satisfied, in the order of the statechart. The update is
    at the last state of the unbroken run of satisfied states, so a state that
    is satisfied is skipped. Refreshing the ddock and the packages is never
    satisfied before this run does it, so an update always replaces the source
    folder; building the node application is never satisfied either, so it
    runs every time.
    """

    def __init__(self) -> None:
        self._capability_loader: CapabilityLoader = CapabilityLoader()

    def evaluate(
        self,
        context: CliContextPort,
    ) -> SystemUpdateProcessStatePort:
        reached_state: SystemUpdateProcessStatePort = SystemUpdateProcessState.UNDEFINED
        state_name: str
        for state_name in SystemUpdateStatechart.sequence():
            state: SystemUpdateProcessStatePort = SystemUpdateProcessState.get_state(state_name)
            capability_type: Any = self._capability_loader.get(
                "org.ontobdc.ddock.plugin.capability.transformation.target."
                f"{state.value.strip('_')}"
            )
            if capability_type is None:
                raise ValueError(f"System update capability not found for state: {state.value}")

            is_satisfied: Any = getattr(capability_type(), "is_satisfied", None)
            try:
                satisfied: bool = callable(is_satisfied) and is_satisfied(context)
            except Exception:
                # What a state reads may not be there yet (no valid system.obdc);
                # the state itself then runs and reports the error.
                satisfied = False
            if not satisfied:
                return reached_state

            reached_state = state

        return reached_state


class SystemUpdateStateTransitionHandler(SystemUpdateStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        # Fails before anything runs when the container is not there.
        SystemUpdateRequest.container_path(context)

        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: SystemUpdateStateEvaluatorPort = (
            SystemUpdateStateEvaluatorAdapter()
        )
        self._active_state: Optional[SystemUpdateProcessStatePort] = None
        self._observed_state: Optional[SystemUpdateProcessStatePort] = None

    @property
    def current_state(self) -> SystemUpdateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> SystemUpdateProcessStatePort:
        """
        The state the update has reached, read once per machine step and held
        until something can have changed it.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: SystemUpdateProcessStatePort) -> bool:
        active_state: SystemUpdateProcessStatePort = self.current_state
        if active_state == SystemUpdateProcessState.UNDEFINED:
            return to_state == SystemUpdateProcessState.SYSTEM_DESCRIPTOR_VALID

        return active_state != to_state

    def perform_state_transition(
        self, to_state: SystemUpdateProcessStatePort
    ) -> None:
        if self.observed_state == to_state:
            return

        self._logger.log_info(
            f"System update transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.ddock.plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"System update capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: SystemUpdateProcessStatePort,
        to_state: SystemUpdateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        state_sequence: List[str] = SystemUpdateStatechart.sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_sequence and observed_name != "undefined":
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the system "
                "update statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the system "
                "update statechart."
            )
        if observed_name == "undefined":
            return False

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def execute(self) -> CommandResponse:
        """
        Run the update from the state the container is in to its last. The
        ddock of the repository of system.obdc and its packages are downloaded
        again into the work folder of the container, the source folder is
        replaced by them, and the node application is built again. The folder
        is removed as soon as the container has everything it lists, whether or
        not the update went on to the end.
        """
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=SystemUpdateProcessState,
            state_context_name="SystemUpdateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=SystemUpdateStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller
            # needs the error itself, such as a missing system.obdc.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        finally:
            self._remove_work_folder_when_installed()

        return CommandResponse(
            title="System Updated",
            description="The system was updated in the container and its node application was compiled again.",
            content={
                "container_path": str(SystemUpdateRequest.container_path(self._context)),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _remove_work_folder_when_installed(self) -> None:
        """
        Remove the work folder once the container has all the files the lock
        lists: nothing in it is needed to go on from there.
        """
        container_path: Path = SystemUpdateRequest.container_path(self._context)
        try:
            descriptor: SystemDescriptor = SystemDescriptors.read(container_path)
        except (FileNotFoundError, ValueError):
            return

        if SystemLock.installed(container_path, descriptor):
            shutil.rmtree(SystemUpdateRequest.work_path(self._context), ignore_errors=True)

    def bind_active_state(self, state: SystemUpdateProcessStatePort) -> None:
        self._active_state = state
