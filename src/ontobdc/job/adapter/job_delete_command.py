from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    ListCommandResponse,
)
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.storage.adapter.repository import LoadedStorageGraph


class JobDeleteCommand(CliCommandPort):
    """
    What the commands that delete jobs have in common: a flag, and the container it works on: the one that
    ``--container`` selects, or every container the storage registers when it is not given, as the listing does.

    A command that deletes says its flag (``FLAG``), what it is called (``TITLE``, and ``DONE`` for what it did), and how it deletes the jobs of
    a container (``delete``).
    """

    COMPONENT: ClassVar[str] = "job"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    CONTAINER_ID_KEY: ClassVar[str] = "container_id"
    FLAG: ClassVar[str]
    TITLE: ClassVar[str]
    DONE: ClassVar[str]

    @staticmethod
    def delete(container_path: Path, container_id: str) -> List[Dict[str, Any]]:
        """Deletes the jobs of the container that the command deletes, and gives them."""
        raise NotImplementedError

    @classmethod
    def accepts(cls, args: List[str]) -> bool:
        """Match the command at the CLI routing stage."""
        return bool(args) and args[0] == cls.COMPONENT and cls._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid. A container that was asked for and does not exist is an error, never the
        whole storage.
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

    @classmethod
    def _matches(cls, scoped_args: List[str]) -> bool:
        """Whether these scoped args are the flag, and ``--container <id-or-path>`` if it is given, in any order."""
        if scoped_args.count(cls.FLAG) != 1:
            return False

        remaining: List[str] = [arg for arg in scoped_args if arg != cls.FLAG]
        if not remaining:
            return True

        return len(remaining) == 2 and remaining[0] == cls.CONTAINER_FLAG and bool(remaining[1].strip())

    def run(self) -> CommandResponse:
        deleted: List[Dict[str, Any]] = []
        containers: List[Tuple[str, Path]] = []
        try:
            containers = self._containers()
            container_id: str
            container_path: Path
            for container_id, container_path in containers:
                try:
                    deleted.extend(self.delete(container_path, container_id))
                except Exception as error:
                    raise RuntimeError(f"Container {container_id}: {error}") from error
        except Exception as error:
            return ExceptionCommandResponse(
                title=f"Failed to {self.TITLE} Jobs",
                description=f"An error occurred while deleting the jobs: {error}",
                content={"jobs": deleted, "error": str(error)},
            )

        return ListCommandResponse(
            title=f"Jobs {self.DONE}",
            description=f"Deleted {len(deleted)} job(s) in {len(containers)} container(s).",
            content={"jobs": deleted},
        )

    def _containers(self) -> List[Tuple[str, Path]]:
        """The container asked for, or every container the storage registers."""
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
