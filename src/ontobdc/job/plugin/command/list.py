from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    ListCommandResponse,
)
from ontobdc.job.adapter.job_listing import ContainerJobs
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.repository import LoadedStorageGraph


class JobListCommand(CliCommandPort):
    """
    Command for listing the jobs that have not finished.

    Without ``--container`` it lists the active jobs of every container the
    storage registers; with it, only those of that container.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="job_list",
        logical_component="job",
        description="List the jobs of every container, or of one container: the active ones, the finished ones or all.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the only container whose active jobs are listed, "
                    "by storage identifier or filesystem path. When omitted, "
                    "the active jobs of every registered container are "
                    "listed."
                ),
                "type": "str",
            },
            {
                "accepts": ["--list", "-l"],
                "description": (
                    "List the jobs that have not finished: the ones whose run "
                    "has a status the job ontology lists as active."
                ),
                "usage": "ontobdc job --list [--finished | --all] [--container <id-or-path>]",
            },
            {
                "accepts": ["--finished"],
                "description": (
                    "With --list, list the jobs that have finished: the ones whose run has a status the "
                    "job ontology lists as finished."
                ),
            },
            {
                "accepts": ["--all"],
                "description": "With --list, list every job, finished or not.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "job"
    LIST_FLAGS: ClassVar[List[str]] = ["--list", "-l"]
    CONTAINER_FLAG: ClassVar[str] = "--container"
    FILTER_FLAGS: ClassVar[Dict[str, str]] = {"--finished": ContainerJobs.FINISHED, "--all": ContainerJobs.ALL}
    CONTAINER_KEY: ClassVar[str] = "container_path"
    CONTAINER_ID_KEY: ClassVar[str] = "container_id"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the job listing at the CLI routing stage.
        """
        return bool(args) and args[0] == JobListCommand.COMPONENT and JobListCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid. A container that was asked for and does
        not exist is an error, never the whole storage.
        """
        command_args: List[str] = self._request.command_args
        if not self._matches(command_args):
            return False

        if self.CONTAINER_FLAG in command_args:
            container_path: Any = self._request.context.get_parameter_value(self.CONTAINER_KEY)
            if not (isinstance(container_path, str) and container_path.strip()):
                selector: str = command_args[command_args.index(self.CONTAINER_FLAG) + 1]
                raise CliCommandArgumentException(f"Container not found: {selector}.")

        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are a list flag, with ``--finished`` or ``--all`` (not both) and
        ``--container <id-or-path>`` if they are given, in any order.
        """
        flags: List[str] = [arg for arg in scoped_args if arg in JobListCommand.LIST_FLAGS]
        if len(flags) != 1:
            return False

        filters: List[str] = [arg for arg in scoped_args if arg in JobListCommand.FILTER_FLAGS]
        if len(filters) > 1:
            return False

        remaining: List[str] = [arg for arg in scoped_args if arg not in flags and arg not in filters]
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == JobListCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> CommandResponse:
        """
        List the active jobs, container by container.
        """
        try:
            kind: str = self._kind()
            status = ContainerJobs.status_of(kind)
            containers: List[Tuple[str, Path]] = self._containers()
            jobs: List[Dict[str, Any]] = []
            container_id: str
            container_path: Path
            for container_id, container_path in containers:
                try:
                    jobs.extend(ContainerJobs.of(container_path, container_id, status))
                except Exception as error:
                    raise RuntimeError(f"Container {container_id}: {error}") from error

        except Exception as error:
            return ExceptionCommandResponse(
                title="Failed to List Jobs",
                description=f"An error occurred while listing the jobs: {error}",
                content={"jobs": [], "error": str(error)},
            )

        return ListCommandResponse(
            title="Jobs",
            description=(
                f"Found {len(jobs)} {'' if kind == ContainerJobs.ALL else kind + ' '}job(s) "
                f"in {len(containers)} container(s)."
            ),
            content={"jobs": jobs},
        )

    def _kind(self) -> str:
        """
        The kind of job to list: the active ones, unless --finished or --all says otherwise.
        """
        asked: List[str] = [self.FILTER_FLAGS[arg] for arg in self._request.command_args if arg in self.FILTER_FLAGS]
        return asked[0] if asked else ContainerJobs.ACTIVE

    def _containers(self) -> List[Tuple[str, Path]]:
        """
        The container asked for, or every container the storage registers.
        """
        if self.CONTAINER_FLAG in self._request.command_args:
            return [
                (
                    str(self._request.context.get_parameter_value(self.CONTAINER_ID_KEY)),
                    Path(str(self._request.context.get_parameter_value(self.CONTAINER_KEY))),
                )
            ]

        storage_graph: LoadedStorageGraph = LoadedStorageGraph(StorageFileLocator.resolve())
        return [
            (str(subject), Path(container_config_dir).expanduser().parent.resolve())
            for subject, container_config_dir, _ in storage_graph.containers
        ]
