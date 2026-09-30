from typing import Callable, Dict, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.storage.adapter.file import StorageFileLocator
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
    ListCommandResponse,
)


class ContainerBaseCommand(CliCommandPort):
    """
    Base command for the container plugin.
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="container",
        description="Base Container command handler.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--list",
                    "-l",
                ],
                "description": (
                    "Print the list of every storage container currently "
                    "registered in the root storage index, along with the "
                    "metadata each container declares."
                ),
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the component root command and its list flags.
        """
        return (
            len(args) >= 1
            and args[0] == "container"
            and (len(args) == 1 or args[1] in ["--list", "-l"])
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._print_log: Optional[Callable[[str], None]] = None

    def set_print_log(self, print_log: Callable[[str], None]) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return (len(self._request.command_args) == 0 or (
            len(self._request.command_args) == 1
            and self._request.command_args[0] in ["--list", "-l"]
        ))

    def run(self) -> CommandResponse:
        """
        List every container registered in the storage graph.
        """
        try:
            storage_graph: LoadedStorageGraph = LoadedStorageGraph(
                StorageFileLocator.resolve()
            )
            containers: List[Dict[str, Optional[str]]] = (
                storage_graph.storage_graph.list_containers()
            )

        except Exception as e:
            return ExceptionCommandResponse(
                title="Failed to List Containers",
                description=f"An error occurred while reading storage.ttl: {str(e)}",
                content={"containers": [], "error": str(e)}
            )

        return ListCommandResponse(
            title="Containers",
            description=f"Found {len(containers)} container(s) in the storage.",
            content={"containers": containers}
        )
