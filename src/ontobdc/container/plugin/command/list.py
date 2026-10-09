from typing import ClassVar, Dict, List, Optional

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


class ContainerListCommand(CliCommandPort):
    """
    List every storage container currently registered in the root storage
    index, along with the metadata each container declares.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_list",
        logical_component="container",
        description=(
            "List every storage container currently registered in the "
            "root storage index."
        ),
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
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    LIST_FLAGS: ClassVar[List[str]] = ["--list", "-l"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the component's list flags at the CLI routing stage.
        """
        return (
            len(args) == 2
            and args[0] == ContainerListCommand.COMPONENT
            and args[1] in ContainerListCommand.LIST_FLAGS
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        return len(command_args) == 1 and command_args[0] in self.LIST_FLAGS

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
