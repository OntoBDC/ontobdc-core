from pathlib import Path
from typing import Any, List, Optional, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.machine.state import CliInitProcessState
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.machine import (
    CliInitProcessStatePort,
    CliInitStateEvaluatorPort,
    CliInitStateTransitionHandlerPort,
)
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.cli.plugin.check.has_valid_engine.check import main as check_engine
from ontobdc.storage.plugin.check.is_root_set.check import main as check_storage_index
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.cli.plugin.check.has_valid_config_file.check import main as check_config_file
from ontobdc.context.plugin.check.has_valid_context.check import main as check_execution_context


class CliInitStateEvaluatorAdapter(CliInitStateEvaluatorPort):
    @property
    def process_state_class(self) -> Type[CliInitProcessStatePort]:
        return CliInitProcessState

    def evaluate(self, context: CliContextPort) -> CliInitProcessStatePort:
        root_path: Path = StorageBootstrap.get_init_root_path(context=context)
        ontobdc_directory: Path = StorageBootstrap.get_ontobdc_directory(root_path)
        if not ontobdc_directory.is_dir():
            return CliInitProcessState.UNDEFINED

        if check_engine(root_path=str(root_path)) != 0:
            return CliInitProcessState.ONTOBDC_DIRECTORY_READY

        if check_storage_index(root_path=str(root_path)) != 0:
            return CliInitProcessState.ENGINE_READY

        if check_execution_context(root_path=str(root_path)) != 0:
            return CliInitProcessState.STORAGE_INDEX_HEALTHY

        if check_config_file(root_path=str(root_path)) != 0:
            return CliInitProcessState.EXECUTION_CONTEXT_HEALTHY

        return CliInitProcessState.CONFIG_ADAPTER_READY


class CliInitStateTransitionHandler(CliInitStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: CliInitStateEvaluatorPort = CliInitStateEvaluatorAdapter()
        self._active_state: Optional[CliInitProcessStatePort] = None

    @property
    def current_state(self) -> CliInitProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> CliInitProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[CliInitProcessStatePort]:
        return list(CliInitProcessState)

    def can_transit_to(self, to_state: CliInitProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: CliInitProcessStatePort) -> None:
        self._logger.log_info(
            f"CLI init transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            f"org.ontobdc.cli.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"CLI init capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: CliInitProcessStatePort,
        to_state: CliInitProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        observed_state: CliInitProcessStatePort = self.observed_state
        if observed_state == to_state:
            return True

        state_sequence: List[CliInitProcessStatePort] = self.state_sequence
        if to_state not in state_sequence or observed_state not in state_sequence:
            return False

        return state_sequence.index(observed_state) > state_sequence.index(to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=CliInitProcessState,
            state_context_name="CliInitProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()

        root_path: Path = StorageBootstrap.get_init_root_path(context=self._context)
        self._logger.log_notice("OntoBDC init bootstrap finished successfully.")
        return CommandResponse(
            title="Init",
            description="Bootstrap initialization executed successfully.",
            content={
                "root_path": str(root_path),
                "ontobdc_directory": str(StorageBootstrap.get_ontobdc_directory(root_path)),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_init.yaml"

    def bind_active_state(self, state: CliInitProcessStatePort) -> None:
        self._active_state = state
