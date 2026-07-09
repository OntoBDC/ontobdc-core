
from typing import Dict, List
from ontobdc.storage import is_enabled
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


class StorageListCommand(CliCommandPort):
    """
    Command for listing storage resources.
    """
    METADATA = CliCommandMetadata(
        id="list",
        logical_component="storage",
        description="List all containers in the storage.",
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": "Display the help message for the list command.",
                "usage": "ontobdc storage --help",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage list command at the CLI routing stage.
        """
        return len(args) > 1 and args[0] == "storage" and args[1] in ["--help", "-h"]

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
        return (
            is_enabled()
            and len(self._request.command_args) == 1
            and self._request.command_args[0] in ["--help", "-h"]
        )

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if len(self._request.command_args) == 1 and self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException()

        arg_list: Dict[str, str] = {}
        usage_list: Dict[str, str] = {"base": "ontobdc storage <argument> [flags/parameters]"}
        loader: PluginResource = CommandLoader('storage')
        for command in loader.get_all():
            if command.METADATA.id != 'base' and hasattr(command.METADATA, 'arguments') and command.METADATA.arguments:
                arg_key = " | ".join(command.METADATA.arguments[0]["accepts"])
                arg_list[arg_key] = command.METADATA.arguments[0]["description"]
                if "usage" in command.METADATA.arguments[0]:
                    usage_list[command.METADATA.id] = command.METADATA.arguments[0]["usage"]

        arg_list[" | ".join(self.METADATA.arguments[0]["accepts"])] = self.METADATA.arguments[0]["description"]

        return HelpCommandResponse(
            title="Storage CLI Help",
            description="Display help information for the storage component.",
            content={
                "Usage": usage_list,
                "Options": arg_list,
            }
        )
