import os
from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.ddock.plugin.machine.system_update.machine import (
    SystemUpdateRequest,
    SystemUpdateStateTransitionHandler,
)


class DdockUpdateCommand(CliCommandPort):
    """
    Command for updating a system: ddock, its packages and the node build.

    ``--update`` downloads again the ddock of the GitHub repository that the
    ``system.obdc`` of the current directory names, replaces the source folder
    of the container with it, downloads its packages again, rewrites the lock
    and builds the node application again, through the system update machine.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ddock_update",
        logical_component="ddock",
        description="Update the ddock and the packages of the system of the current directory from its system.obdc.",
        arguments=[
            {
                "accepts": ["--update"],
                "description": (
                    "Download again the ddock of the repository of system.obdc and its "
                    "packages, and build the node application again."
                ),
                "type": "bool",
                "usage": "ontobdc ddock --update",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ddock"
    UPDATE_FLAG: ClassVar[str] = "--update"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the update command at the CLI routing stage.
        """
        if not args or args[0] != DdockUpdateCommand.COMPONENT:
            return False

        return DdockUpdateCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid: it has the shape of the command.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Match --update on its own.
        """
        return scoped_args == [DdockUpdateCommand.UPDATE_FLAG]

    def run(self) -> CommandResponse:
        """
        Update the system of the current directory: run the machine of the
        update, from the validation of ``system.obdc`` to the build of the
        node application.
        """
        context: Any = self._request.context
        context.set_parameter_value(SystemUpdateRequest.CONTAINER_PATH_KEY, os.getcwd())
        try:
            return SystemUpdateStateTransitionHandler(context).execute()
        finally:
            context.delete_parameter(SystemUpdateRequest.CONTAINER_PATH_KEY)
            context.delete_parameter(SystemUpdateRequest.BUILT_KEY)
