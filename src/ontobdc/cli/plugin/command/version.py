from typing import List
from importlib.metadata import version as get_version

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
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
                    "version",
                    "-v",
                ],
                "description": (
                    "Print the version string reported by the active "
                    "ontobdc Python package installation."
                ),
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

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

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
        version: str = "unknown"

        try:
            version = get_version("ontobdc")
        except Exception:
            pass

        return CommandResponse(
            title="Version",
            description="Display the package version.",
            content={
                "version": version
            }
        )
