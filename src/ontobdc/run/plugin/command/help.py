
from typing import Dict
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, HelpCommandResponse
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource


class RunHelpCommand(CliCommandPort):
    """
    Help command for run plugin
    """
    METADATA = CliCommandMetadata(
        id="help",
        logical_component="run",
        description="Display help for run commands.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": "Display help information",
            }
        ],
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
        return True

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if len(self._request.command_args) == 1 and self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException()

        arg_list: Dict[str, str] = {}
        usage_list: Dict[str, str] = {"base": "ontobdc run <argument> [flags/parameters]"}
        loader: PluginResource = CommandLoader('run')
        for command in loader.get_all():
            if command.METADATA.id != 'help' and hasattr(command.METADATA, 'arguments') and command.METADATA.arguments:
                arg_key = " | ".join(command.METADATA.arguments[0]["accepts"])
                arg_list[arg_key] = command.METADATA.arguments[0]["description"]
                if "usage" in command.METADATA.arguments[0]:
                    usage_list[command.METADATA.id] = command.METADATA.arguments[0]["usage"]

        arg_list[" | ".join(self.METADATA.arguments[0]["accepts"])] = self.METADATA.arguments[0]["description"]

        return HelpCommandResponse(
            title="Run CLI Help",
            description="Display help information for the run component.",
            content={
                "Usage": usage_list,
                "Options": arg_list,
            }
        )
