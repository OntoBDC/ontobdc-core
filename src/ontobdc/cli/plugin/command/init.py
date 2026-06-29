from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse


class CliInitCommand(CliCommandPort):
    """
    Command to initialize the ontobdc configuration in a project.
    """
    METADATA = CliCommandMetadata(
        id="init",
        logical_component="cli",
        description="Initialize ontobdc in the current directory.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "init",
                ],
                "description": "Initialize ontobdc in the current directory.",
            },
        ],
    )

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
        return len(self._request.command_args) >= 1 and self._request.command_args[0] == 'init'

    def run(self) -> CommandResponse:
        """
        Execute the command to initialize the ontobdc environment.
        """
        
