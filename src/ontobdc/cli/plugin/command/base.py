
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, HelpCommandResponse


class CliBaseCommand(CliCommandPort):
    """
    Helper class for base command loading.
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="cli",
        description="Base CLI command handler.",
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return False

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if len(self._request.command_args) != 1 or self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException()

        command_list = {}

        return HelpCommandResponse(
            title="CLI Help",
            description="Display help information for the CLI.",
            content={
                "Usage": ["ontobdc <command> [flags/parameters]"],
                "Commands": command_list,
            }
        )
        
