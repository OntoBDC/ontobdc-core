from dataclasses import replace
from typing import Any, Callable, ClassVar, Dict, List, Optional
from pathlib import Path
import importlib

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.handler import StateTransitionHandlerPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.plugin.machine.init.port import (
    CliInitProcessStatePort,
    CliInitStateEvaluatorPort,
    CliInitStateTransitionHandlerPort,
)
from ontobdc.cli.plugin.machine.init.state import CliInitProcessState
from ontobdc.cli.plugin.machine.init.statechart import CliInitStatechart
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class CliInitStateEvaluatorAdapter(CliInitStateEvaluatorPort):
    """
    Reads the project on disk and reports the state it is already in.

    The states come from the statechart, in order, and each one resolves its
    check by the ``is_<state>.check.main`` convention. The project is in the
    last state whose check holds, provided that every state before it holds
    too.
    """

    CHECK_MODULE_PREFIX: ClassVar[str] = "ontobdc.cli.plugin.check.is_"

    def evaluate(self, context: CliContextPort) -> CliInitProcessStatePort:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        reached_state: CliInitProcessStatePort = CliInitProcessState.UNDEFINED
        state_name: str
        for state_name in CliInitStatechart.sequence()[1:]:
            state: CliInitProcessStatePort = CliInitProcessState.get_state(state_name)
            if self._check_for(state)(root_path=str(root_path)) != 0:
                return reached_state

            reached_state = state

        return reached_state

    @classmethod
    def _check_for(cls, state: CliInitProcessStatePort) -> Callable[..., int]:
        module_name: str = f"{cls.CHECK_MODULE_PREFIX}{state.value.strip('_')}.check"
        check: Any = getattr(importlib.import_module(module_name), "main")
        if not callable(check):
            raise TypeError(f"CLI init state check is not callable: {module_name}.main")

        return check


class CliInitStateTransitionHandler(CliInitStateTransitionHandlerPort):
    """
    Drive the CLI init statechart.

    Each transition resolves the capability of its target state, executes it,
    and counts only if the project, read again from disk, is in that state or
    beyond it. When a ``next_handler`` is given it runs once the project has
    genuinely reached the final state, and never otherwise.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "CliInitProcessStatePort"
    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.ontobdc.cli.plugin.capability.transformation.target."
    )
    FINAL_STATE: ClassVar[CliInitProcessStatePort] = CliInitProcessState.BRAND_READY

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        next_handler: Optional[StateTransitionHandlerPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._next_handler: Optional[StateTransitionHandlerPort] = next_handler
        self._state_evaluator: CliInitStateEvaluatorPort = CliInitStateEvaluatorAdapter()
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._active_state: Optional[CliInitProcessStatePort] = None
        self._observed_state: Optional[CliInitProcessStatePort] = None

    @property
    def next_handler(self) -> Optional[StateTransitionHandlerPort]:
        return self._next_handler

    @property
    def current_state(self) -> CliInitProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> CliInitProcessStatePort:
        """
        The state the project is in on disk, read again after every capability.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: CliInitProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: CliInitProcessStatePort) -> None:
        if self._rank(self.observed_state) >= self._rank(to_state):
            return

        self._logger.log_info(
            f"CLI init transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{to_state.value.strip('_')}"
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(f"CLI init capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(capability, self._context)
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: CliInitProcessStatePort,
        to_state: CliInitProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._rank(self.observed_state) >= self._rank(to_state)

    def bind_active_state(self, state: CliInitProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=CliInitProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=CliInitStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise

        self._observed_state = None
        reached_state: CliInitProcessStatePort = self.observed_state
        if reached_state != self.FINAL_STATE:
            raise RuntimeError(
                f"OntoBDC init stopped at state '{reached_state.value}' "
                f"instead of '{self.FINAL_STATE.value}'."
            )

        root_path: Path = StorageBootstrap.get_init_root_path(context=self._context)
        content: Dict[str, Any] = {
            "root_path": str(root_path),
            "ontobdc_directory": str(StorageBootstrap.get_ontobdc_directory(root_path)),
            "current_state": reached_state.value,
            "visited_states": visited_states,
        }
        self._logger.log_notice("OntoBDC init bootstrap finished successfully.")
        response: CommandResponse = CommandResponse(
            title="Init",
            description="Bootstrap initialization executed successfully.",
            content=content,
        )
        if self._next_handler is None:
            return response

        chained: CommandResponse = self._next_handler.execute()
        return replace(chained, content={**chained.content, "ontobdc": content})

    @staticmethod
    def _rank(state: CliInitProcessStatePort) -> int:
        return CliInitStatechart.sequence().index(state.value.strip("_"))
