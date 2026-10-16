from pathlib import Path
from typing import Any, Dict, List, Optional

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from ontobdc.container.domain.model.remote import RemoteContainerUrl
from ontobdc.container.plugin.machine.container_remote.port import (
    RemoteContainerProcessStatePort,
    RemoteContainerStateEvaluatorPort,
    RemoteContainerStateTransitionHandlerPort,
)
from ontobdc.container.plugin.machine.container_remote.state import RemoteContainerProcessState
from ontobdc.container.plugin.machine.container_remote.statechart import RemoteContainerStatechart


def _load_state_capability(
    loader: CapabilityLoader,
    state: RemoteContainerProcessStatePort,
) -> CapabilityPort:
    capability_id: str = RemoteContainerStatechart.capability_id(state)
    capability_type: Any = loader.get(capability_id)
    if capability_type is None:
        raise ValueError(f"Remote container capability not found: {capability_id}")

    return capability_type()


class RemoteContainerStateEvaluatorAdapter(RemoteContainerStateEvaluatorPort):
    """
    Reads what is on disk and reports the state the connection is already in.

    Each non-terminal state resolves its own capability and asks whether
    that capability already considers itself satisfied. Reachability is a
    terminal, re-verified action rather than a persisted fact — the remote
    answering once does not mean it still answers now — so it is never
    treated as already reached.
    """

    def __init__(self) -> None:
        self._capability_loader: CapabilityLoader = CapabilityLoader()

    def evaluate(self, context: CliContextPort) -> RemoteContainerProcessStatePort:
        reached_state: RemoteContainerProcessStatePort = RemoteContainerProcessState.UNDEFINED
        state_name: str
        for state_name in RemoteContainerStatechart.sequence()[1:]:
            state: RemoteContainerProcessStatePort = RemoteContainerProcessState.get_state(state_name)
            if RemoteContainerStatechart.is_terminal(state):
                return reached_state

            capability: CapabilityPort = _load_state_capability(self._capability_loader, state)
            is_satisfied: Any = getattr(capability, "is_satisfied", None)
            if not callable(is_satisfied) or not is_satisfied(context):
                return reached_state

            reached_state = state

        return reached_state


class RemoteContainerStateTransitionHandler(RemoteContainerStateTransitionHandlerPort):
    """
    Drive the remote container statechart.

    Each transition resolves the capability of its target state by id and
    executes it; a non-terminal transition counts only if the connection,
    read again from disk, is in that state or beyond it.
    """

    STATE_CONTEXT_NAME: str = "RemoteContainerProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._state_evaluator: RemoteContainerStateEvaluatorPort = (
            RemoteContainerStateEvaluatorAdapter()
        )
        self._active_state: Optional[RemoteContainerProcessStatePort] = None
        self._observed_state: Optional[RemoteContainerProcessStatePort] = None
        self._last_performed_state: Optional[RemoteContainerProcessStatePort] = None

    @property
    def current_state(self) -> RemoteContainerProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> RemoteContainerProcessStatePort:
        """
        The state the connection is in on disk, read again after every capability.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: RemoteContainerProcessStatePort) -> bool:
        if self.current_state == RemoteContainerProcessState.REMOTE_CONTAINER_REACHABLE:
            return to_state == self._expected_storage_root_state()

        return self.current_state != to_state

    def _expected_storage_root_state(self) -> RemoteContainerProcessStatePort:
        """
        Which of the two storage root branches applies right now.

        A real storage root is used when one is found; otherwise a
        temporary one is initialized so the connection can still complete.
        """
        capability: CapabilityPort = _load_state_capability(
            self._capability_loader,
            RemoteContainerProcessState.STORAGE_ROOT_RECOVERED,
        )
        is_satisfied: Any = getattr(capability, "is_satisfied", None)
        if callable(is_satisfied) and is_satisfied(self._context):
            return RemoteContainerProcessState.STORAGE_ROOT_RECOVERED

        return RemoteContainerProcessState.TEMP_STORAGE_ROOT_INITIALIZED

    def perform_state_transition(self, to_state: RemoteContainerProcessStatePort) -> None:
        if (
            not RemoteContainerStatechart.is_terminal(to_state)
            and self.observed_state == to_state
        ):
            return

        self._logger.log_info(
            f"Storage container remote transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = _load_state_capability(self._capability_loader, to_state)
        try:
            CapabilityExecutor.execute(capability, self._context)
            self._last_performed_state = to_state
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: RemoteContainerProcessStatePort,
        to_state: RemoteContainerProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        if to_state in (
            RemoteContainerProcessState.STORAGE_ROOT_RECOVERED,
            RemoteContainerProcessState.TEMP_STORAGE_ROOT_INITIALIZED,
            RemoteContainerProcessState.CONTAINER_CREATED,
            RemoteContainerProcessState.CONTAINER_FILES_DOWNLOADED,
        ):
            # None of the four is ever observable from disk: reachability,
            # right before all of them, has no persisted fact of its own and
            # is always re-verified, so the evaluator can never walk past
            # it. Success here can only be confirmed by having just
            # performed it.
            return self._last_performed_state == to_state

        if RemoteContainerStatechart.is_terminal(to_state):
            return self._last_performed_state == to_state

        sequence: List[str] = RemoteContainerStatechart.sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "remote container statechart."
            )
        if target_name not in sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the remote "
                "container statechart."
            )

        return sequence.index(observed_name) >= sequence.index(target_name)

    def bind_active_state(self, state: RemoteContainerProcessStatePort) -> None:
        self._active_state = state
        self._observed_state = None

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=RemoteContainerProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=RemoteContainerStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        url: str = str(self._context.get_parameter_value("remote_url")).strip()
        destination: Path = RemoteContainerUrl.destination(
            url, self._context.get_parameter_value("remote_download_dir")
        )
        content: Dict[str, Any] = {
            "url": url,
            "path": str(destination),
            "size": destination.stat().st_size,
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        self._logger.log_notice("Storage container remote connection finished successfully.")

        return CommandResponse(
            title="Remote Container Reachable",
            description="The remote container file is downloaded and its information is available.",
            content=content,
        )
