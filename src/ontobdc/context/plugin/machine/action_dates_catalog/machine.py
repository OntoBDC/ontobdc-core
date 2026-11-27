from pathlib import Path
from typing import Any, Dict, List, Optional

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from ontobdc.context.plugin.machine.action_dates_catalog.etl import ActionDatesCatalogEtlEvent
from ontobdc.context.plugin.machine.action_dates_catalog.port import (
    ActionDatesCatalogProcessStatePort,
    ActionDatesCatalogStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.action_dates_catalog.state import ActionDatesCatalogProcessState
from ontobdc.context.plugin.machine.action_dates_catalog.statechart import ActionDatesCatalogStatechart


def _load_state_capability(
    loader: CapabilityLoader,
    state: ActionDatesCatalogProcessStatePort,
) -> CapabilityPort:
    capability_id: str = ActionDatesCatalogStatechart.capability_id(state)
    capability_type: Any = loader.get(capability_id)
    if capability_type is None:
        raise ValueError(f"Action dates catalog capability not found: {capability_id}")

    return capability_type()


class ActionDatesCatalogStateTransitionHandler(ActionDatesCatalogStateTransitionHandlerPort):
    """
    Drive the statechart that catalogs the dates of the actions in a container.

    The only state after the initial one is terminal, and nothing on disk says it was reached:
    a day that exists does not mean the files of its date are all related to it. So the
    machine always performs it, and counts it only if it has just been performed.
    """

    STATE_CONTEXT_NAME: str = "ActionDatesCatalogProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._active_state: Optional[ActionDatesCatalogProcessStatePort] = None
        self._last_performed_state: Optional[ActionDatesCatalogProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> ActionDatesCatalogProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ActionDatesCatalogProcessStatePort:
        """
        The state the machine reached. Nothing on disk tells the cataloging is done, so it starts from
        the initial state, and after that it is the state that was just performed.
        """
        if self._last_performed_state is not None:
            return self._last_performed_state

        return ActionDatesCatalogProcessState.UNDEFINED

    def can_transit_to(self, to_state: ActionDatesCatalogProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: ActionDatesCatalogProcessStatePort) -> None:
        self._logger.log_info(
            f"Action dates catalog transition: {self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = _load_state_capability(self._capability_loader, to_state)
        self._result = CapabilityExecutor.execute(capability, self._context)
        ActionDatesCatalogEtlEvent.write(
            Path(RequiredParameter.of(self._context, "container_path")).expanduser().resolve(),
            str(RequiredParameter.of(self._context, "procedure_iri")),
            to_state,
            self._result,
        )
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: ActionDatesCatalogProcessStatePort,
        to_state: ActionDatesCatalogProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: ActionDatesCatalogProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ActionDatesCatalogProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=ActionDatesCatalogStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        content: Dict[str, Any] = {
            "created": self._result["created"],
            "updated": self._result["updated"],
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        self._logger.log_notice("The dates of the actions in the container were cataloged.")

        return CommandResponse(
            title="Days Cataloged",
            description="Each date of the files of the container has its day, with the files related to it.",
            content=content,
        )
