from typing import Dict, List
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, HelpCommandResponse

class DevBaseCommand(CliCommandPort):
    """
    Base command for dev plugin. Equivalent to dev --help | -h.
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="dev",
        description="Display help information for the dev component.",
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": "Display help information for the dev component.",
                "usage": "ontobdc dev --help",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dev base command at the CLI routing stage.
        Accepts `dev`, `dev -h`, and `dev --help`.
        """
        if not args or args[0] != "dev":
            return False

        return len(args) == 1 or args[1] in ["--help", "-h"]

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
        return len(self._request.command_args) == 0 or (
            len(self._request.command_args) == 1
            and self._request.command_args[0] in ["--help", "-h"]
        )

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if len(self._request.command_args) == 1 and self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException(f"Invalid arguments for dev base: {self._request.command_args}")

        arg_list: Dict[str, str] = {}
        usage_list: Dict[str, str] = {"base": "ontobdc dev <argument> [flags/parameters]"}
        
        loader: PluginResource = CommandLoader('dev')
        for command in loader.get_all():
            if command.METADATA.id != 'base' and hasattr(command.METADATA, 'arguments') and command.METADATA.arguments:
                arg_key = " | ".join(command.METADATA.arguments[0]["accepts"])
                arg_list[arg_key] = command.METADATA.arguments[0]["description"]
                if "usage" in command.METADATA.arguments[0]:
                    usage_list[command.METADATA.id] = command.METADATA.arguments[0]["usage"]

        arg_list[" | ".join(self.METADATA.arguments[0]["accepts"])] = self.METADATA.arguments[0]["description"]

        return HelpCommandResponse(
            title="Dev CLI Help",
            description="Display help information for the dev component.",
            content={
                "Usage": usage_list,
                "Options": arg_list,
            }
        )
