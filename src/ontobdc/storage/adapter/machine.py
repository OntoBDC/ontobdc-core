from pathlib import Path
from typing import Any, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse, ExceptionCommandResponse
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.shared.adapter.loader import CapabilityLoader
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.storage.domain.machine.state import (
    ContainerCreateProcessState,
    ContainerUpdateProcessState,
    DatasetCreateProcessState,
)
from ontobdc.storage.domain.port.machine import (
    ContainerCreateProcessStatePort,
    ContainerCreateStateEvaluatorPort,
    ContainerCreateStateTransitionHandlerPort,
    ContainerUpdateProcessStatePort,
    ContainerUpdateStateEvaluatorPort,
    ContainerUpdateStateTransitionHandlerPort,
    DatasetCreateProcessStatePort,
    DatasetCreateStateEvaluatorPort,
    DatasetCreateStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.capability.transformation.container_cleaned import (
    ContainerCleanedCapability,
)
from ontobdc.storage.plugin.check.is_container_cleaned.check import (
    evaluate as evaluate_container_cleaned,
)
from ontobdc.storage.plugin.check.is_container_datapackage_updated.check import (
    evaluate as evaluate_container_datapackage_updated,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.storage.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)


class ContainerCreateStateEvaluatorAdapter(ContainerCreateStateEvaluatorPort):
    @property
    def process_state_class(self) -> Type[ContainerCreateProcessStatePort]:
        return ContainerCreateProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerCreateProcessStatePort:
        target_path: Path = Path(context.get_parameter_value("container_path")).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()

        if target_path.exists() and not target_path.is_dir():
            return ContainerCreateProcessState.INVALID_PATH

        if target_path.exists() and target_path.is_dir():
            metadata_check_result: int = check_container_metadata_ready(
                root_path=str(root_path),
                container_path=str(target_path),
            )
            if metadata_check_result == 0:
                if (
                    check_container_storage_index_ready(
                        root_path=str(root_path),
                        container_path=str(target_path),
                    )
                    == 0
                ):
                    if (
                        check_container_manifest_synced(
                            root_path=str(root_path),
                            container_path=str(target_path),
                        )
                        == 0
                    ):
                        return ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED

                    return ContainerCreateProcessState.CONTAINER_STORAGE_INDEX_READY

                return ContainerCreateProcessState.CONTAINER_METADATA_READY

            return ContainerCreateProcessState.DIRECTORY_READY

        return ContainerCreateProcessState.UNDEFINED


class ContainerCreateStateTransitionHandler(ContainerCreateStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = Path(self._context.get_parameter_value("container_path")).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: ContainerCreateStateEvaluatorPort = ContainerCreateStateEvaluatorAdapter()
        self._active_state: Optional[ContainerCreateProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ContainerCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ContainerCreateProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ContainerCreateProcessStatePort]:
        return list(ContainerCreateProcessState)

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

    def perform_state_transition(self, to_state: ContainerCreateProcessStatePort) -> None:
        observed_state: ContainerCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"Storage container create transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            f"org.ontobdc.storage.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Storage container create capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: ContainerCreateProcessStatePort,
        to_state: ContainerCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        observed_state: ContainerCreateProcessStatePort = self.observed_state
        return observed_state == to_state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ContainerCreateProcessState,
            state_context_name="ContainerCreateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
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

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_container_create.yaml"

    def bind_active_state(self, state: ContainerCreateProcessStatePort) -> None:
        self._active_state = state


class ContainerUpdateStateEvaluatorAdapter(ContainerUpdateStateEvaluatorPort):
    def __init__(
        self,
        cleanup_capability: Optional[ContainerCleanedCapability] = None,
    ) -> None:
        self._cleanup_capability: ContainerCleanedCapability = (
            cleanup_capability or ContainerCleanedCapability()
        )

    @property
    def process_state_class(self) -> Type[ContainerUpdateProcessStatePort]:
        return ContainerUpdateProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerUpdateProcessStatePort:
        raw_container_path: Any = context.get_parameter_value("container_path")
        if not isinstance(raw_container_path, (str, Path)):
            return ContainerUpdateProcessState.CONTAINER_INVALID

        target_path: Path = Path(raw_container_path).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()
        if not target_path.is_dir():
            return ContainerUpdateProcessState.CONTAINER_INVALID

        metadata_result: int = check_container_metadata_ready(
            root_path=str(root_path),
            container_path=str(target_path),
        )
        storage_index_result: int = check_container_storage_index_ready(
            root_path=str(root_path),
            container_path=str(target_path),
        )
        if metadata_result != 0 or storage_index_result != 0:
            return ContainerUpdateProcessState.UNDEFINED

        # Best-effort, not re-checked here: a dataset with no known repair
        # path (see DatasetHealthyCapability) must not block this state
        # forever, so this is a "ran once" flag, the same contract
        # container_html_view_updated uses.
        if not bool(
            context.get_parameter_value("container_datasets_healthy")
        ):
            return ContainerUpdateProcessState.CONTAINER_HEALTHY

        cleanup_result: int = evaluate_container_cleaned(
            container_path=str(target_path),
            file_names=self._cleanup_capability.file_names_to_clean,
        )
        if cleanup_result == 2:
            return ContainerUpdateProcessState.CONTAINER_INVALID
        if cleanup_result != 0:
            return ContainerUpdateProcessState.CONTAINER_DATASETS_HEALTHY

        datapackage_result: int = evaluate_container_datapackage_updated(
            str(target_path)
        )
        if datapackage_result == 2:
            return ContainerUpdateProcessState.CONTAINER_INVALID
        if datapackage_result != 0:
            return ContainerUpdateProcessState.CONTAINER_CLEANED

        if (
            check_container_manifest_synced(
                root_path=str(root_path),
                container_path=str(target_path),
            )
            != 0
        ):
            return ContainerUpdateProcessState.CONTAINER_DATAPACKAGE_UPDATED

        if bool(context.get_parameter_value("container_update_completed")):
            return ContainerUpdateProcessState.CONTAINER_UPDATED

        index_path: Path = target_path / "index.html"
        if (
            index_path.is_file()
            and bool(
                context.get_parameter_value(
                    "container_html_view_updated"
                )
            )
        ):
            return ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED

        return ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED


class ContainerUpdateStateTransitionHandler(
    ContainerUpdateStateTransitionHandlerPort
):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        cleanup_capability: Optional[ContainerCleanedCapability] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = Path(
            self._context.get_parameter_value("container_path")
        ).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._cleanup_capability: ContainerCleanedCapability = (
            cleanup_capability or ContainerCleanedCapability()
        )
        self._state_evaluator: ContainerUpdateStateEvaluatorPort = (
            ContainerUpdateStateEvaluatorAdapter(
                cleanup_capability=self._cleanup_capability,
            )
        )
        self._active_state: Optional[ContainerUpdateProcessStatePort] = None
        self._last_transition_state: Optional[
            ContainerUpdateProcessStatePort
        ] = None
        self._clear_process_markers()

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> ContainerUpdateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ContainerUpdateProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[ContainerUpdateProcessStatePort]:
        return list(ContainerUpdateProcessState)

    def can_transit_to(
        self,
        to_state: ContainerUpdateProcessStatePort,
    ) -> bool:
        active_state: ContainerUpdateProcessStatePort = self.current_state

        if active_state == ContainerUpdateProcessState.UNDEFINED:
            expected_state: ContainerUpdateProcessStatePort = (
                ContainerUpdateProcessState.CONTAINER_INVALID
                if self.observed_state == ContainerUpdateProcessState.CONTAINER_INVALID
                else ContainerUpdateProcessState.CONTAINER_HEALTHY
            )
            return to_state == expected_state

        if (
            active_state
            == ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED
        ):
            index_exists: bool = (self._target_path / "index.html").is_file()
            expected_state = (
                ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED
                if index_exists
                else ContainerUpdateProcessState.CONTAINER_UPDATED
            )
            return to_state == expected_state

        return active_state != to_state

    def perform_state_transition(
        self,
        to_state: ContainerUpdateProcessStatePort,
    ) -> None:
        self._last_transition_state = None
        observed_state: ContainerUpdateProcessStatePort = self.observed_state

        self._logger.log_info(
            f"Storage container update transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )

        if self._state_reaches(observed_state, to_state):
            self._last_transition_state = to_state
            return

        if to_state == ContainerUpdateProcessState.CONTAINER_CLEANED:
            capability: CapabilityPort = self._cleanup_capability
        else:
            capability_id: str = (
                "org.ontobdc.storage.plugin.capability.transformation.target."
                f"{to_state.value.strip('_')}"
            )
            capability_type: Any = CapabilityLoader().get(capability_id)
            if capability_type is None:
                raise ValueError(
                    "Storage container update capability not found: "
                    f"{capability_id}"
                )

            capability = capability_type()

        CapabilityExecutor.execute(capability, self._context)
        self._last_transition_state = to_state

    def validate_state_transition(
        self,
        from_state: ContainerUpdateProcessStatePort,
        to_state: ContainerUpdateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False
        if self._last_transition_state != to_state:
            return False

        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ContainerUpdateProcessState,
            state_context_name="ContainerUpdateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if (
            self.current_state
            == ContainerUpdateProcessState.CONTAINER_INVALID
        ):
            return ExceptionCommandResponse(
                title="Invalid Storage Container",
                description=(
                    "The target container is structurally invalid and cannot "
                    "be updated automatically."
                ),
                content={
                    "container_id": str(
                        self._context.get_parameter_value("container_id")
                    ),
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="Storage Container Updated",
            description=(
                "The container was cleaned, its Data Package and RO-Crate "
                "metadata were updated, and its existing HTML view was "
                "updated when present."
            ),
            content={
                "container_id": str(
                    self._context.get_parameter_value("container_id")
                ),
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "html_view_updated": bool(
                    self._context.get_parameter_value(
                        "container_html_view_updated"
                    )
                ),
            },
        )

    def _get_statechart_file_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "domain"
            / "machine"
            / "standard_container_update.yaml"
        )

    def _state_reaches(
        self,
        observed_state: ContainerUpdateProcessStatePort,
        target_state: ContainerUpdateProcessStatePort,
    ) -> bool:
        if observed_state == target_state:
            return True
        if (
            observed_state
            == ContainerUpdateProcessState.CONTAINER_INVALID
            or target_state
            == ContainerUpdateProcessState.CONTAINER_INVALID
        ):
            return False

        ordered_states: List[ContainerUpdateProcessStatePort] = [
            ContainerUpdateProcessState.UNDEFINED,
            ContainerUpdateProcessState.CONTAINER_HEALTHY,
            ContainerUpdateProcessState.CONTAINER_DATASETS_HEALTHY,
            ContainerUpdateProcessState.CONTAINER_CLEANED,
            ContainerUpdateProcessState.CONTAINER_DATAPACKAGE_UPDATED,
            ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED,
            ContainerUpdateProcessState.CONTAINER_HTML_VIEW_UPDATED,
            ContainerUpdateProcessState.CONTAINER_UPDATED,
        ]
        try:
            return ordered_states.index(observed_state) >= ordered_states.index(
                target_state
            )
        except ValueError:
            return False

    def _clear_process_markers(self) -> None:
        for parameter_name in (
            "container_html_view_updated",
            "container_datasets_healthy",
            "container_update_completed",
        ):
            if self._context.has_parameter(parameter_name):
                self._context.delete_parameter(parameter_name)

    def bind_active_state(
        self,
        state: ContainerUpdateProcessStatePort,
    ) -> None:
        self._active_state = state


class DatasetCreateStateEvaluatorAdapter(DatasetCreateStateEvaluatorPort):
    @property
    def process_state_class(self) -> Type[DatasetCreateProcessStatePort]:
        return DatasetCreateProcessState

    def evaluate(
        self,
        context: CliContextPort,
    ) -> DatasetCreateProcessStatePort:
        target_path: Path = Path(context.get_parameter_value("dataset_path")).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()
        if target_path.exists() and not target_path.is_dir():
            return DatasetCreateProcessState.INVALID_PATH

        if target_path.exists() and target_path.is_dir():
            metadata_check_result: int = check_dataset_metadata_ready(
                dataset_path=str(target_path),
                root_path=str(root_path),
            )
            if metadata_check_result == 0:
                if (
                    check_dataset_container_index_ready(
                        dataset_path=str(target_path),
                        root_path=str(root_path),
                    )
                    == 0
                ):
                    return DatasetCreateProcessState.DATASET_CONTAINER_INDEX_READY

                return DatasetCreateProcessState.DATASET_METADATA_READY

            return DatasetCreateProcessState.DIRECTORY_READY

        return DatasetCreateProcessState.UNDEFINED


class DatasetCreateStateTransitionHandler(DatasetCreateStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = Path(self._context.get_parameter_value("dataset_path")).expanduser().resolve()
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DatasetCreateStateEvaluatorPort = DatasetCreateStateEvaluatorAdapter()
        self._active_state: Optional[DatasetCreateProcessStatePort] = None

    @property
    def context(self) -> CliContextPort:
        return self._context

    @property
    def target_path(self) -> Path:
        return self._target_path

    @property
    def current_state(self) -> DatasetCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> DatasetCreateProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    @property
    def state_sequence(self) -> List[DatasetCreateProcessStatePort]:
        return list(DatasetCreateProcessState)

    def can_transit_to(self, to_state: DatasetCreateProcessStatePort) -> bool:
        active_state: DatasetCreateProcessStatePort = self.current_state
        if active_state == DatasetCreateProcessState.UNDEFINED:
            expected_state: DatasetCreateProcessStatePort = (
                DatasetCreateProcessState.INVALID_PATH
                if self.observed_state == DatasetCreateProcessState.INVALID_PATH
                else DatasetCreateProcessState.DIRECTORY_READY
            )
            return to_state == expected_state

        return active_state != to_state

    def perform_state_transition(self, to_state: DatasetCreateProcessStatePort) -> None:
        observed_state: DatasetCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"Storage dataset create transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            f"org.ontobdc.storage.plugin.capability.transformation.target.{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Storage dataset create capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        CapabilityExecutor.execute(capability, self._context)

    def validate_state_transition(
        self,
        from_state: DatasetCreateProcessStatePort,
        to_state: DatasetCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        observed_state: DatasetCreateProcessStatePort = self.observed_state
        return observed_state == to_state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DatasetCreateProcessState,
            state_context_name="DatasetCreateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == DatasetCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid Storage Dataset Path",
                description="The target path points to an existing file and cannot become a dataset directory.",
                content={
                    "container_id": str(self._context.get_parameter_value("container_id")),
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="Storage Dataset Created",
            description="The local storage dataset directory, dataset metadata, and container dataset entry are ready for the next creation steps.",
            content={
                "container_id": str(self._context.get_parameter_value("container_id")),
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )

    def _get_statechart_file_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "domain" / "machine" / "standard_dataset_create.yaml"

    def bind_active_state(self, state: DatasetCreateProcessStatePort) -> None:
        self._active_state = state
