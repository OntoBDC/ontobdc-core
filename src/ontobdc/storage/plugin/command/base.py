
from ontobdc.storage import get_storage_file
from typing import Callable, Dict, List, Optional
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.response.command import CommandResponse, ListCommandResponse, ExceptionCommandResponse


class StorageBaseCommand(CliCommandPort):
    """
    Base command for storage plugin
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="storage",
        description="Base Storage command handler.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--list",
                    "-l",
                ],
                "description": "List all containers in the storage.",
                "usage": "ontobdc storage --list",
            }
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the component root command and its help flags.
        """
        return (
            len(args) >= 1
            and args[0] == "storage"
            and (len(args) == 1 or args[1] in ["--list", "-l"])
        )

    def __init__(self, request: CliCommandRequest):
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
        Execute the command.
        """
        try:
            storage_graph = LoadedStorageGraph(get_storage_file())
            containers: List[Dict[str, Optional[str]]] = storage_graph.storage_graph.list_containers()

        except Exception as e:
            return ExceptionCommandResponse(
                title="Failed to List Containers",
                description=f"An error occurred while reading storage.ttl: {str(e)}",
                content={"containers": [], "error": str(e)}
            )

        return ListCommandResponse(
            title="Storage Containers",
            description=f"Found {len(containers)} container(s) in the storage.",
            content={"containers": containers}
        )
