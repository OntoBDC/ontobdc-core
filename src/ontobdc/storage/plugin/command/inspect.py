from typing import ClassVar, List
from pathlib import Path

from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class StorageInspectCommand(CliCommandPort):
    """
    Command for reporting the storage root the current execution runs under.

    It owns exactly one surface: the resolved root path, exposed as the
    ``root_path`` field of the standard command response, so the resolution
    every other command performs implicitly becomes inspectable on demand.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="storage_inspect",
        logical_component="storage",
        description="Report the storage root of the current execution.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--inspect",
                ],
                "description": (
                    "Print the storage root the current execution runs "
                    "under, resolved the same way every command resolves "
                    "it."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "storage"
    INSPECT_FLAGS: ClassVar[List[str]] = ["--inspect"]

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match ``storage --inspect`` at the CLI routing stage.
        """
        return (
            len(args) == 2
            and args[0] == StorageInspectCommand.COMPONENT
            and args[1] in StorageInspectCommand.INSPECT_FLAGS
        )

    def check(self) -> bool:
        """
        Validate the scoped arguments carry exactly the inspection flag.
        """
        command_args: List[str] = self._request.command_args

        return len(command_args) == 1 and command_args[0] in self.INSPECT_FLAGS

    def run(self) -> CommandResponse:
        """
        Resolve the storage root and return it as the response content.
        """
        root_path: Path = StorageBootstrap.get_init_root_path(
            context=self._request.context
        )

        return CommandResponse(
            title="Storage Inspection",
            description="Storage root of the current execution.",
            content={
                "root_path": str(root_path),
            },
        )
