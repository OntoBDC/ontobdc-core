from typing import Any, Dict, List, Optional
from pathlib import Path

import yaml

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
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshProcessStatePort,
    ContainerRefreshStateEvaluatorPort,
    ContainerRefreshStateTransitionHandlerPort,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.container.plugin.machine.container_refresh.state import (
    ContainerRefreshProcessState,
)
from ontobdc.container.plugin.check.is_container_cleaned.check import (
    evaluate as evaluate_container_cleaned,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.container.plugin.capability.transformation.container_cleaned import (
    ContainerCleanedCapability,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.check import (
    evaluate as evaluate_container_datapackage_updated,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


class ContainerRefreshStateEvaluatorAdapter(ContainerRefreshStateEvaluatorPort):
    def __init__(
        self,
        cleanup_capability: Optional[ContainerCleanedCapability] = None,
    ) -> None:
        self._cleanup_capability: ContainerCleanedCapability = (
            cleanup_capability or ContainerCleanedCapability()
        )

    def evaluate(
        self,
        context: CliContextPort,
    ) -> ContainerRefreshProcessStatePort:
        raw_container_path: Any = context.get_parameter_value("container_path")
        if not isinstance(raw_container_path, (str, Path)):
            return ContainerRefreshProcessState.CONTAINER_INVALID

        target_path: Path = Path(raw_container_path).expanduser().resolve()
        root_path: Path = Path(context.root_path).expanduser().resolve()
        if not target_path.is_dir():
            return ContainerRefreshProcessState.CONTAINER_INVALID

        metadata_result: int = check_container_metadata_ready(
            root_path=str(root_path),
            container_path=str(target_path),
        )
        storage_index_result: int = check_container_storage_index_ready(
            root_path=str(root_path),
            container_path=str(target_path),
        )
        if metadata_result != 0 or storage_index_result != 0:
            return ContainerRefreshProcessState.UNDEFINED

        state_sequence: List[str] = (
            ContainerRefreshStateTransitionHandler._state_sequence()
        )
        reached_state: ContainerRefreshProcessStatePort = (
            ContainerRefreshProcessState.CONTAINER_HEALTHY
        )
        healthy_index: int = state_sequence.index(reached_state.value.strip("_"))
        events_directory: Path = (
            ContainerRefreshStateTransitionHandler._refresh_events_directory(
                target_path
            )
        )
        state_name: str
        for state_name in state_sequence[healthy_index + 1 :]:
            state_enum: ContainerRefreshProcessStatePort = (
                ContainerRefreshProcessState.get_state(state_name)
            )
            if not self._state_was_reached(
                state_enum=state_enum,
                state_name=state_name,
                container_path=target_path,
                root_path=root_path,
                cleanup_capability=self._cleanup_capability,
                events_directory=events_directory,
            ):
                return reached_state
            reached_state = state_enum

        return reached_state

    @staticmethod
    def _state_was_reached(
        *,
        state_enum: ContainerRefreshProcessStatePort,
        state_name: str,
        container_path: Path,
        root_path: Path,
        cleanup_capability: ContainerCleanedCapability,
        events_directory: Path,
    ) -> bool:
        event_value: str = state_enum.value
        if not isinstance(event_value, str) or not event_value.strip():
            raise TypeError(
                "Container refresh state enum entry must expose a non-empty "
                f"string 'value'; got {type(state_enum)!r} -> {event_value!r}."
            )
        event_candidate: Path = events_directory / f"{event_value}.json"
        if state_name in {"container_datasets_healthy", "container_updated"}:
            return event_candidate.is_file()

        if state_name == "container_cleaned":
            return (
                evaluate_container_cleaned(
                    container_path=str(container_path),
                    file_names=cleanup_capability.file_names_to_clean,
                )
                == 0
            )

        if state_name == "container_datapackage_updated":
            return evaluate_container_datapackage_updated(str(container_path)) == 0

        if state_name == "container_ro_crate_updated":
            return (
                check_container_manifest_synced(
                    root_path=str(root_path),
                    container_path=str(container_path),
                )
                == 0
            )

        if state_name in {"container_invalid", "undefined"}:
            return False
        return False


class ContainerRefreshStateTransitionHandler(
    ContainerRefreshStateTransitionHandlerPort
):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
        cleanup_capability: Optional[ContainerCleanedCapability] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = (
            Path(self._context.get_parameter_value("container_path"))
            .expanduser()
            .resolve()
        )
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._cleanup_capability: ContainerCleanedCapability = (
            cleanup_capability or ContainerCleanedCapability()
        )
        self._state_evaluator: ContainerRefreshStateEvaluatorPort = (
            ContainerRefreshStateEvaluatorAdapter(
                cleanup_capability=self._cleanup_capability,
            )
        )
        self._active_state: Optional[ContainerRefreshProcessStatePort] = None
        self._last_transition_state: Optional[ContainerRefreshProcessStatePort] = None

    @property
    def current_state(self) -> ContainerRefreshProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> ContainerRefreshProcessStatePort:
        return self._state_evaluator.evaluate(self._context)

    def can_transit_to(
        self,
        to_state: ContainerRefreshProcessStatePort,
    ) -> bool:
        active_state: ContainerRefreshProcessStatePort = self.current_state

        if active_state == ContainerRefreshProcessState.UNDEFINED:
            expected_state: ContainerRefreshProcessStatePort = (
                ContainerRefreshProcessState.CONTAINER_INVALID
                if self.observed_state == ContainerRefreshProcessState.CONTAINER_INVALID
                else ContainerRefreshProcessState.CONTAINER_HEALTHY
            )
            return to_state == expected_state

        return active_state != to_state

    def perform_state_transition(
        self,
        to_state: ContainerRefreshProcessStatePort,
    ) -> None:
        self._last_transition_state = None
        observed_state: ContainerRefreshProcessStatePort = self.observed_state
        if observed_state == to_state:
            self._last_transition_state = to_state
            return

        self._logger.log_info(
            f"Storage container refresh transition: "
            f"{self.current_state.value} -> {to_state.value}",
        )

        if to_state == ContainerRefreshProcessState.CONTAINER_CLEANED:
            capability: CapabilityPort = self._cleanup_capability
        else:
            capability_id: str = (
                "org.ontobdc.container.plugin.capability.transformation.target."
                f"{to_state.value.strip('_')}"
            )
            capability_type: Any = CapabilityLoader().get(capability_id)
            if capability_type is None:
                raise ValueError(
                    f"Storage container refresh capability not found: {capability_id}"
                )

            capability = capability_type()

        CapabilityExecutor.execute(
            capability,
            self._context,
            StrategyParamResolver(ResolverLoader()),
        )
        self._last_transition_state = to_state

    @classmethod
    def _refresh_events_directory(cls, container_path: Path) -> Path:
        resolved: Path = Path(container_path).expanduser().resolve()
        return (
            StorageBootstrap.get_ontobdc_directory(resolved)
            / "etl"
            / "container"
            / "refresh"
            / "container"
        )

    @classmethod
    def _state_sequence(cls) -> List[str]:
        root_state: Dict[str, Any] = cls._statechart_data()["statechart"]["root state"]
        states_by_name: Dict[str, Dict[str, Any]] = {
            state["name"]: state for state in root_state["states"]
        }

        initial_name: Any = root_state.get("initial")
        if not isinstance(initial_name, str) or not initial_name:
            raise ValueError(
                "Container refresh statechart must declare a root initial state."
            )
        current_name: str = initial_name
        sequence: List[str] = [current_name]
        while "transitions" in states_by_name.get(current_name, {}):
            transitions: Any = states_by_name[current_name]["transitions"]
            if not isinstance(transitions, list) or not transitions:
                break

            valid_targets: List[Any] = []
            transition: Any
            for transition in transitions:
                if not isinstance(transition, dict):
                    continue
                target: Any = transition.get("target")
                if isinstance(target, str) and target:
                    valid_targets.append(target)

            if not valid_targets:
                break
            if len(valid_targets) > 1:
                operational_target: Optional[str] = None
                target_name: Any
                for target_name in valid_targets:
                    if target_name == "container_invalid":
                        continue
                    operational_target = target_name
                if operational_target is None:
                    if "container_invalid" in valid_targets:
                        operational_target = "container_invalid"
                if operational_target is None:
                    raise ValueError(
                        "Container refresh statechart cannot resolve an "
                        "operational transition target from state "
                        f"'{current_name}'."
                    )
                current_name = operational_target
            else:
                current_name = valid_targets[0]
            sequence.append(current_name)

        return sequence

    @classmethod
    def _statechart_data(cls) -> Dict[str, Any]:
        statechart_data: Any = yaml.safe_load(
            cls._get_statechart_file_path().read_text(encoding="utf-8")
        )
        if not isinstance(statechart_data, dict):
            raise TypeError("Container refresh statechart must be a mapping.")

        return statechart_data

    @classmethod
    def _get_statechart_file_path(cls) -> Path:
        return StatechartLocator.locate(
            "ontobdc.container.plugin.machine.container_refresh",
            "standard_container_refresh.yaml",
        )

    @staticmethod
    def _state_reaches(
        observed_state: ContainerRefreshProcessStatePort,
        target_state: ContainerRefreshProcessStatePort,
    ) -> bool:
        state_sequence: List[str] = (
            ContainerRefreshStateTransitionHandler._state_sequence()
        )
        observed_name: str = observed_state.value.strip("_")
        target_name: str = target_state.value.strip("_")
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "container refresh statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the container "
                "refresh statechart."
            )

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def validate_state_transition(
        self,
        from_state: ContainerRefreshProcessStatePort,
        to_state: ContainerRefreshProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._state_reaches(self.observed_state, to_state)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=ContainerRefreshProcessState,
            state_context_name="ContainerRefreshProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=self._get_statechart_file_path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == ContainerRefreshProcessState.CONTAINER_INVALID:
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
                "The container was cleaned, and its Data Package and "
                "RO-Crate metadata were updated."
            ),
            content={
                "container_id": str(self._context.get_parameter_value("container_id")),
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def bind_active_state(
        self,
        state: ContainerRefreshProcessStatePort,
    ) -> None:
        self._active_state = state
