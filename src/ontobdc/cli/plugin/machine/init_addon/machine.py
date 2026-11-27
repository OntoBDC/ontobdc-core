from typing import Any, Dict, List, Optional

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.plugin.machine.init_addon.port import (
    CliInitAddonProcessStatePort,
    CliInitAddonStateTransitionHandlerPort,
)
from ontobdc.cli.plugin.machine.init_addon.request import CliInitAddonRequest
from ontobdc.cli.plugin.machine.init_addon.state import CliInitAddonProcessState
from ontobdc.cli.plugin.machine.init_addon.statechart import CliInitAddonStatechart
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort


class CliInitAddonStateTransitionHandler(CliInitAddonStateTransitionHandlerPort):
    """
    Drive the statechart that adds an addon.

    Nothing on disk says a state was reached: the addon is located again every time. So the machine always performs a
    state, and counts it only if it has just been performed.
    """

    STATE_CONTEXT_NAME: str = "CliInitAddonProcessStatePort"
    CAPABILITY_ID_PREFIX: str = "org.ontobdc.cli.plugin.capability.transformation.target."
    DESCRIPTIONS: Dict[str, str] = {
        "installed": "The addon {name} was installed in the storage.",
        "replaced": "The addon {name} was installed in the storage, in place of the folder that was there.",
        "restored": "The addon {name} was copied again to the storage, which had it but not its folder.",
        "already": "The addon {name} was already installed in the storage.",
    }

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._active_state: Optional[CliInitAddonProcessStatePort] = None
        self._last_performed_state: Optional[CliInitAddonProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> CliInitAddonProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> CliInitAddonProcessStatePort:
        if self._last_performed_state is not None:
            return self._last_performed_state

        return CliInitAddonProcessState.UNDEFINED

    def can_transit_to(self, to_state: CliInitAddonProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: CliInitAddonProcessStatePort) -> None:
        self._logger.log_info(f"CLI init addon transition: {self.current_state.value} -> {to_state.value}")
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(f"CLI init addon capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        self._result = CapabilityExecutor.execute(capability, self._context)
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: CliInitAddonProcessStatePort,
        to_state: CliInitAddonProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: CliInitAddonProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        # The addon is what the process works on: without it nothing is done.
        CliInitAddonRequest.source(self._context)
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=CliInitAddonProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=CliInitAddonStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        content: Dict[str, Any] = {
            "name": self._result["name"],
            "addon": self._result["addon"],
            "installed": self._result["installed"],
            "action": self._result["action"],
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        description: str = self.DESCRIPTIONS[self._result["action"]].format(name=self._result["name"])
        self._logger.log_notice(description)

        return CommandResponse(title="Addon Added", description=description, content=content)
