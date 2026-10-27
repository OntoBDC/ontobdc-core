from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

import yaml

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader, ResolverLoader
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort

from ontobdc.storage.plugin.machine.file_reconciliation.port import (
    FileReconciliationProcessStatePort,
    FileReconciliationStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.machine.file_reconciliation.state import (
    FileReconciliationProcessState,
)


class FileReconciliationStateTransitionHandler(
    FileReconciliationStateTransitionHandlerPort
):
    """
    Drive the file reconciliation statechart.

    Every state is an action of the current invocation: the files are looked at again each time the
    reconciliation is asked for, so no state is observed as already reached, and each is validated
    by having been performed. Each state runs the capability whose id is the prefix plus the name
    of the state. The first two states only find out; the last records, in the history of the RO-Crate,
    what the files are now.
    """

    STATE_CONTEXT_NAME: ClassVar[str] = "FileReconciliationProcessStatePort"
    CAPABILITY_ID_PREFIX: ClassVar[str] = (
        "org.ontobdc.storage.plugin.capability.transformation.target."
    )
    STATECHART_PACKAGE: ClassVar[str] = (
        "ontobdc.storage.plugin.machine.file_reconciliation"
    )
    STATECHART_FILE: ClassVar[str] = "standard_file_reconciliation.yaml"
    FINAL_STATE: ClassVar[FileReconciliationProcessStatePort] = (
        FileReconciliationProcessState.DATASET_HISTORY_RECORDED
    )

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        capability_root_packages: Tuple[str, ...] = (
            CapabilityLoader.DEFAULT_ROOT_PACKAGES
        ),
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._resolver: StrategyParamResolver = StrategyParamResolver(
            ResolverLoader(root_packages=capability_root_packages)
        )
        self._capability_loader: CapabilityLoader = CapabilityLoader(
            root_packages=capability_root_packages
        )
        self._active_state: FileReconciliationProcessStatePort = (
            FileReconciliationProcessState.UNDEFINED
        )
        self._last_performed_state: Optional[FileReconciliationProcessStatePort] = None
        self._result: Dict[str, Any] = {}

    @property
    def current_state(self) -> FileReconciliationProcessStatePort:
        return self._active_state

    def can_transit_to(self, to_state: FileReconciliationProcessStatePort) -> bool:
        return self._active_state != to_state

    def perform_state_transition(
        self,
        to_state: FileReconciliationProcessStatePort,
    ) -> None:
        capability: CapabilityPort = self._capability(to_state)
        self._logger.log_info(
            "File reconciliation transition: "
            f"{self._active_state.value} -> {to_state.value}",
        )
        # Each state adds what it found to what the ones before it found.
        self._result = {
            **self._result,
            **CapabilityExecutor.execute(capability, self._context, self._resolver),
        }
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: FileReconciliationProcessStatePort,
        to_state: FileReconciliationProcessStatePort,
    ) -> bool:
        return from_state != to_state and self._last_performed_state == to_state

    def bind_active_state(self, state: FileReconciliationProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> Dict[str, Any]:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=FileReconciliationProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=self.statechart_file_path(),
        )
        try:
            worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller needs the error itself.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        if self._last_performed_state != self.FINAL_STATE:
            reached: str = (
                self._last_performed_state.value
                if self._last_performed_state is not None
                else self._active_state.value
            )
            raise RuntimeError(
                f"File reconciliation stopped at state '{reached}' "
                f"instead of '{self.FINAL_STATE.value}'."
            )
        return dict(self._result)

    @classmethod
    def statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(cls.STATECHART_PACKAGE, cls.STATECHART_FILE)

    @classmethod
    def state_sequence(cls) -> List[str]:
        return StateWorkerAdapter.compute_state_sequence(
            yaml.safe_load(cls.statechart_file_path().read_text(encoding="utf-8"))
        )

    def _capability(
        self,
        state: FileReconciliationProcessStatePort,
    ) -> CapabilityPort:
        capability_id: str = f"{self.CAPABILITY_ID_PREFIX}{state.value.strip('_')}"
        capability_type: Any = self._capability_loader.get(capability_id)
        if capability_type is None:
            raise ValueError(
                "File reconciliation capability not found for state: "
                f"{state.value} (id: {capability_id})"
            )
        return capability_type()
