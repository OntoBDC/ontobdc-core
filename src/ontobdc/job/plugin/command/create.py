import re
from pathlib import Path
from typing import Any, ClassVar, List, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.job.adapter.job_executor import JobExecutor
from ontobdc.job.plugin.machine.job_create.machine import (
    JobCreateRequest,
    JobCreateStateTransitionHandler,
)
from ontobdc.shared.adapter.parameter import RequiredParameter


class JobCreateCommand(CliCommandPort):
    """
    Command for creating a job: the execution of a procedure of a graph that anybody can open.

    The creation goes through a machine of its own, which tests the graph, tests the procedure, finds what the
    procedure targets and makes sure the container has a dataset for jobs, and ends with the job created, its
    run pending. Then the job is handed to the executor, which runs it apart from this command. The flags
    that are not the ones of the command are the parameters of the job, each with its value.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="job_create",
        logical_component="job",
        description="Create a job that executes a procedure of a graph, and start it.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "job_graph_url",
                "description": (
                    "The HTTP(S) address or local filesystem path of the graph that holds the procedure."
                ),
                "type": "str",
                "usage": (
                    "ontobdc job --create <graph URL or path> --procedure <node name> "
                    "[--container <id-or-path>] "
                    "[--<parameter-name> <value>]..."
                ),
            },
            {
                "accepts": ["--procedure"],
                "valued": True,
                "parameter": "job_procedure",
                "description": "The name of the node of the graph that is the procedure.",
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container the job is created in and runs on, by storage identifier or "
                    "filesystem path. When omitted, it is resolved from the current working directory. "
                    "The job needs a container: without one the command fails."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "job"
    CREATE_FLAG: ClassVar[str] = "--create"
    PROCEDURE_FLAG: ClassVar[str] = "--procedure"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    REQUIRED_FLAGS: ClassVar[Tuple[str, ...]] = ("--create", "--procedure")
    BOUND_FLAGS: ClassVar[Tuple[str, ...]] = ("--create", "--procedure", "--container")
    CONTAINER_KEY: ClassVar[str] = "container_path"
    FLAG: ClassVar["re.Pattern[str]"] = re.compile(r"--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the creation of a job at the CLI routing stage.
        """
        return bool(args) and args[0] == JobCreateCommand.COMPONENT and JobCreateCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid. The job needs a container: the one ``--container`` selects, or the one
        the current directory is in, and it must exist.
        """
        command_args: List[str] = self._request.command_args
        if not self._matches(command_args):
            return False

        container_path: Any = self._request.context.get_parameter_value(self.CONTAINER_KEY)
        if not (isinstance(container_path, str) and container_path.strip()):
            if self.CONTAINER_FLAG in command_args:
                raise CliCommandArgumentException(
                    f"Container not found: {command_args[command_args.index(self.CONTAINER_FLAG) + 1]}."
                )
            raise CliCommandArgumentException(
                "The current directory is not in a container: select one with --container."
            )

        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --create and --procedure, and --container if it is given, each
        with a value, then any number of parameters of the job, each a flag with a value, none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        if any(flag not in flags for flag in JobCreateCommand.REQUIRED_FLAGS):
            return False
        if len(set(flags)) != len(flags):
            return False
        if any(not JobCreateCommand.FLAG.fullmatch(flag) for flag in flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        scoped_args: List[str] = self._request.command_args
        parameters: List[Tuple[str, str]] = [
            (flag[2:].replace("-", "_"), value)
            for flag, value in zip(scoped_args[0::2], scoped_args[1::2])
            if flag not in self.BOUND_FLAGS
        ]
        context.set_parameter_value(JobCreateRequest.PARAMETERS_KEY, parameters)
        container_path: Path = Path(RequiredParameter.of(context, self.CONTAINER_KEY)).expanduser().resolve()

        created: CommandResponse = JobCreateStateTransitionHandler(context).execute()
        job_id: str = str(created.content["job_id"])
        worker: int = JobExecutor.start(container_path, job_id)

        return CommandResponse(
            title="Job Created",
            description=f"Created the job {job_id}; it is running apart from this command.",
            content={
                "job_id": job_id,
                "status": "Pending",
                "container": str(container_path),
                "target": created.content["target"],
                "worker": worker,
            },
        )
