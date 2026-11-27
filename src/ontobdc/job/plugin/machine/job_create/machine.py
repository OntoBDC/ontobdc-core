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

from ontobdc.job.adapter.procedure_graph import ProcedureGraph
from ontobdc.job.plugin.machine.job_create.etl import JobCreateEtlEvent
from ontobdc.job.plugin.machine.job_create.port import (
    JobCreateProcessStatePort,
    JobCreateStateTransitionHandlerPort,
)
from ontobdc.job.plugin.machine.job_create.state import JobCreateProcessState
from ontobdc.job.plugin.machine.job_create.statechart import JobCreateStatechart


def _load_state_capability(
    loader: CapabilityLoader,
    state: JobCreateProcessStatePort,
) -> CapabilityPort:
    capability_id: str = JobCreateStatechart.capability_id(state)
    capability_type: Any = loader.get(capability_id)
    if capability_type is None:
        raise ValueError(f"Job create capability not found: {capability_id}")

    return capability_type()


class JobCreateRequest:
    """
    What the creation of a job is given and what its states leave in the command context for the next ones.
    """

    GRAPH_URL_KEY: str = "job_graph_url"
    PROCEDURE_NAME_KEY: str = "job_procedure"
    CONTAINER_PATH_KEY: str = "container_path"
    PARAMETERS_KEY: str = "job_parameters"
    GRAPH_KEY: str = "job_graph"
    PROCEDURE_NODE_KEY: str = "job_procedure_node"
    TARGET_KEY: str = "job_target"
    DATASET_PATH_KEY: str = "job_dataset_path"
    JOB_ID_KEY: str = "job_id"

    @staticmethod
    def required(context: CliContextPort, key: str) -> Any:
        """
        What the context carries under the key.

        Raises:
            ValueError: the context carries nothing under it.
        """
        value: Any = context.get_parameter_value(key)
        if value is None:
            raise ValueError(f"The command context carries no {key}.")

        return value


class JobCreateStateTransitionHandler(JobCreateStateTransitionHandlerPort):
    """
    Drive the statechart that creates a job.

    Each state after the initial one is reached by performing its capability, and nothing on disk says
    it was reached before: the machine always starts from the initial state and counts a state only if
    it has just been performed.
    """

    STATE_CONTEXT_NAME: str = "JobCreateProcessStatePort"

    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._capability_loader: CapabilityLoader = CapabilityLoader()
        self._active_state: Optional[JobCreateProcessStatePort] = None
        self._last_performed_state: Optional[JobCreateProcessStatePort] = None

    @property
    def current_state(self) -> JobCreateProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> JobCreateProcessStatePort:
        """
        The state the machine reached. Nothing on disk tells the creation is done, so it starts from
        the initial state, and after that it is the state that was just performed.
        """
        if self._last_performed_state is not None:
            return self._last_performed_state

        return JobCreateProcessState.UNDEFINED

    def can_transit_to(self, to_state: JobCreateProcessStatePort) -> bool:
        return self.current_state != to_state

    def perform_state_transition(self, to_state: JobCreateProcessStatePort) -> None:
        self._logger.log_info(
            f"Job creation transition: {self.current_state.value} -> {to_state.value}",
        )
        capability: CapabilityPort = _load_state_capability(self._capability_loader, to_state)
        result: Dict[str, Any] = CapabilityExecutor.execute(capability, self._context)
        container_path: Path = Path(
            str(JobCreateRequest.required(self._context, JobCreateRequest.CONTAINER_PATH_KEY))
        ).expanduser().resolve()
        procedure_iri: str = str(
            ProcedureGraph.node(
                JobCreateRequest.required(self._context, JobCreateRequest.GRAPH_KEY),
                str(JobCreateRequest.required(self._context, JobCreateRequest.PROCEDURE_NAME_KEY)),
            )
        )
        JobCreateEtlEvent.write(container_path, procedure_iri, to_state, result)
        self._last_performed_state = to_state

    def validate_state_transition(
        self,
        from_state: JobCreateProcessStatePort,
        to_state: JobCreateProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        return self._last_performed_state == to_state

    def bind_active_state(self, state: JobCreateProcessStatePort) -> None:
        self._active_state = state

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=JobCreateProcessState,
            state_context_name=self.STATE_CONTEXT_NAME,
            handler=self,
            logger=self._logger,
            statechart_file_path=JobCreateStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            cause: Optional[BaseException] = error.__cause__
            if isinstance(cause, Exception):
                raise cause from None
            raise

        content: Dict[str, Any] = {
            "job_id": str(JobCreateRequest.required(self._context, JobCreateRequest.JOB_ID_KEY)),
            "dataset_path": str(JobCreateRequest.required(self._context, JobCreateRequest.DATASET_PATH_KEY)),
            "target": str(JobCreateRequest.required(self._context, JobCreateRequest.TARGET_KEY)),
            "current_state": self.current_state.value,
            "visited_states": visited_states,
        }
        self._logger.log_notice("The job was created.")

        return CommandResponse(
            title="Job Created",
            description="The job is waiting to run.",
            content=content,
        )
