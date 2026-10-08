from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict, List, Optional
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
from ontobdc.container.plugin.machine.dataset_create.port import (
    DatasetCreateProcessStatePort,
    DatasetCreateStateEvaluatorPort,
    DatasetCreateStateTransitionHandlerPort,
)
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.container.plugin.machine.dataset_create.state import (
    DatasetCreateProcessState,
)
from ontobdc.container.plugin.machine.dataset_create.statechart import (
    DatasetCreateStatechart,
)


class DatasetCreateStateEvaluatorAdapter(DatasetCreateStateEvaluatorPort):
    """
    Reads the dataset on disk and reports the state it is already in.

    State order comes directly from the statechart YAML. Every observable
    state resolves its standalone check by the mandatory
    ``is_<state>.check.main`` plugin convention.
    """

    CHECK_MODULE_PREFIX: ClassVar[str] = "ontobdc.container.plugin.check.is_"
    ENTITY_IRI_KEY: ClassVar[str] = "dataset_entity_iri"

    def evaluate(
        self,
        context: CliContextPort,
    ) -> DatasetCreateProcessStatePort:
        """
        Return the state the target dataset directory is already in.
        """
        target_path: Path = (
            Path(context.get_parameter_value("dataset_path")).expanduser().resolve()
        )
        root_path: Path = Path(context.root_path).expanduser().resolve()

        if not target_path.exists():
            return DatasetCreateProcessState.UNDEFINED

        if not target_path.is_dir():
            return DatasetCreateProcessState.INVALID_PATH

        reached_state: DatasetCreateProcessStatePort = (
            DatasetCreateProcessState.DIRECTORY_READY
        )
        state_name: str
        for state_name in DatasetCreateStatechart.sequence()[1:]:
            state: DatasetCreateProcessStatePort = (
                DatasetCreateProcessState.get_state(state_name)
            )
            check: Callable[..., int] = self._check_for(state)
            if (
                check(
                    root_path=str(root_path),
                    dataset_path=str(target_path),
                )
                != 0
            ):
                return reached_state

            reached_state = state

        return reached_state

    @classmethod
    def _entity_arguments(
        cls,
        state: DatasetCreateProcessStatePort,
        context: CliContextPort,
    ) -> Dict[str, str]:
        """
        The entity type the dataset must hold, for the state that records it.
        """
        entity_iri: Any = context.get_parameter_value(cls.ENTITY_IRI_KEY)
        if (
            state != DatasetCreateProcessState.DATASET_METADATA_READY
            or not isinstance(entity_iri, str)
            or not entity_iri.strip()
        ):
            return {}

        return {"entity_iri": entity_iri.strip()}

    @classmethod
    def _check_for(
        cls,
        state: DatasetCreateProcessStatePort,
    ) -> Callable[..., int]:
        state_name: str = state.value.strip("_")
        module_name: str = f"{cls.CHECK_MODULE_PREFIX}{state_name}.check"
        check_module: Any = importlib.import_module(module_name)
        check: Any = getattr(check_module, "main")
        if not callable(check):
            raise TypeError(
                f"Dataset state check is not callable: {module_name}.main"
            )

        return check


class DatasetCreateStateTransitionHandler(DatasetCreateStateTransitionHandlerPort):
    # The directory of a dataset is made by its own capability: the one named
    # after the state makes the directory of a container.
    CAPABILITY_NAMES: ClassVar[Dict[DatasetCreateProcessStatePort, str]] = {
        DatasetCreateProcessState.DIRECTORY_READY: "dataset_directory_ready",
    }

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._target_path: Path = (
            Path(self._context.get_parameter_value("dataset_path"))
            .expanduser()
            .resolve()
        )
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: DatasetCreateStateEvaluatorPort = (
            DatasetCreateStateEvaluatorAdapter()
        )
        self._active_state: Optional[DatasetCreateProcessStatePort] = None
        self._observed_state: Optional[DatasetCreateProcessStatePort] = None

    @property
    def current_state(self) -> DatasetCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> DatasetCreateProcessStatePort:
        """
        The state the dataset is in on disk, read once per machine step.

        Evaluating parses the dataset and the container index, and every
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

    def perform_state_transition(
        self, to_state: DatasetCreateProcessStatePort
    ) -> None:
        observed_state: DatasetCreateProcessStatePort = self.observed_state
        if observed_state == to_state:
            return

        self._logger.log_info(
            f"Storage dataset create transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.container.plugin.capability.transformation.target."
            f"{self.CAPABILITY_NAMES.get(to_state, to_state.value.strip('_'))}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(
                f"Storage dataset create capability not found: {capability_id}"
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
        from_state: DatasetCreateProcessStatePort,
        to_state: DatasetCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        state_sequence: List[str] = DatasetCreateStatechart.sequence()
        observed_state: DatasetCreateProcessStatePort = self.observed_state
        observed_name: str = observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_sequence:
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the "
                "dataset create statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the dataset "
                "create statechart."
            )

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=DatasetCreateProcessState,
            state_context_name="DatasetCreateProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=DatasetCreateStatechart.path(),
        )
        visited_states: List[str] = worker.work()
        return self._build_final_response(visited_states)

    def _build_final_response(self, visited_states: List[str]) -> CommandResponse:
        if self.current_state == DatasetCreateProcessState.INVALID_PATH:
            return ExceptionCommandResponse(
                title="Invalid Storage Dataset Path",
                description="The target path points to an existing file and cannot become a dataset directory.",
                content={
                    "path": str(self._target_path),
                    "current_state": self.current_state.value,
                    "visited_states": visited_states,
                },
            )

        return CommandResponse(
            title="Storage Dataset Created",
            description="The dataset directory, its metadata and its entry in the container index are ready.",
            content={
                "path": str(self._target_path),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
                "exists": self._target_path.exists(),
            },
        )

    def bind_active_state(self, state: DatasetCreateProcessStatePort) -> None:
        self._active_state = state
