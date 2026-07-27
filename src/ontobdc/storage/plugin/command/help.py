from typing import Dict, List, Optional

from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.shared.facade.port.logger import LogRepositoryPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.adapter.logger import NullLogRepository
from ontobdc.shared.facade.exception.command import CliCommandArgumentException
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.response.command import CommandResponse, HelpCommandResponse


class StorageHelpCommand(CliCommandPort):
    """
    Command for displaying help information for the storage component.
    """
    METADATA = CliCommandMetadata(
        id="help",
        logical_component="storage",
        description="Display help information for the storage component.",
        arguments=[
            {
                "accepts": [
                    "--help",
                    "-h",
                ],
                "description": "Display help information for the storage component.",
                "usage": "ontobdc storage --help",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage help command at the CLI routing stage.
        """
        return len(args) > 1 and args[0] == "storage" and args[1] in ["--help", "-h"]

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: Optional[callable] = None
        self._logger: LogRepositoryPort = NullLogRepository()

    def set_print_log(self, print_log: callable) -> None:
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return (len(self._request.command_args) == 1
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
        loader: CommandLoader = CommandLoader("storage", self._logger)
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
