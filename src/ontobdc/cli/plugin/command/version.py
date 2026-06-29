from typing import List

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse


class CliVersionCommand(CliCommandPort):
    """
    Command to display the package version.
    """
    METADATA = CliCommandMetadata(
        id="version",
        logical_component="cli",
        description="Display the version of ontobdc.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--version",
                    "-v",
                ],
                "description": "Display the package version.",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        return len(args) == 1 and args[0] in ['--version', '-v']

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return len(self._request.command_args) == 1 and self._request.command_args[0] in ['--version', '-v']

    def run(self) -> CommandResponse:
        """
        Execute the command to get and return the package version.
        """
        version = "unknown"
        
        try:
            from importlib.metadata import version as get_version
            version = get_version("ontobdc")
        except (ImportError, Exception):
            pass

        return CommandResponse(
            title="OntoBDC Version",
            description="Display the package version.",
            content={
                "version": version
            }
        )
