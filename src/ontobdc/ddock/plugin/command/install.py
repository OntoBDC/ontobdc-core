import os
from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.ddock.plugin.machine.system_install.machine import (
    SystemInstallRequest,
    SystemInstallStateTransitionHandler,
)


class DdockInstallCommand(CliCommandPort):
    """
    Command for installing a system: ddock and its packages.

    ``--install`` names the GitHub repository of ddock by whatever address the
    person has at hand. The install-from-GitHub strategy of the parameter stage
    turns it into the address of the zip of its master branch (else its main
    branch), and ``check`` refuses a command whose address named no repository.
    ``run`` installs, in the current directory, the system that its
    ``system.obdc`` describes, through the system install machine.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ddock_install",
        logical_component="ddock",
        description="Install ddock and the packages of system.obdc into the current directory.",
        arguments=[
            {
                "accepts": ["--install"],
                "valued": True,
                "parameter": "ddock_install_source",
                "description": (
                    "The GitHub repository of ddock, by any address; it is "
                    "installed from the zip of its master branch, else of its main branch."
                ),
                "type": "str",
                "usage": "ontobdc ddock --install <github-address>",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "ddock"
    INSTALL_FLAG: ClassVar[str] = "--install"
    SOURCE_KEY: ClassVar[str] = "ddock_install_source"
    ZIP_KEY: ClassVar[str] = "ddock_install_zip"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the install command at the CLI routing stage.
        """
        if not args or args[0] != DdockInstallCommand.COMPONENT:
            return False

        return DdockInstallCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid: it has the shape of the command, and the
        address it was given resolved to the zip of a GitHub repository.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        zip_address: Any = self._request.context.get_parameter_value(self.ZIP_KEY)
        return isinstance(zip_address, str) and bool(zip_address.strip())

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --install and its value, nothing else.
        """
        return (
            len(scoped_args) == 2
            and scoped_args[0] == DdockInstallCommand.INSTALL_FLAG
            and bool(scoped_args[1].strip())
            and not scoped_args[1].startswith("--")
        )

    def run(self) -> CommandResponse:
        """
        Install the system of the current directory: run the machine of the
        installation, from the validation of ``system.obdc`` to the build of
        the node application.
        """
        context: Any = self._request.context
        context.set_parameter_value(SystemInstallRequest.PROJECT_PATH_KEY, os.getcwd())
        try:
            return SystemInstallStateTransitionHandler(context).execute()
        finally:
            context.delete_parameter(SystemInstallRequest.PROJECT_PATH_KEY)
            context.delete_parameter(SystemInstallRequest.BUILT_KEY)
