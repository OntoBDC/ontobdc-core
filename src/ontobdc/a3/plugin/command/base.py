
from typing import Dict
from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.shared.adapter.plugin import CommandLoader, PluginResource
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.resource.command import CommandResponse, HelpCommandResponse


class A3BaseCommand(CliCommandPort):
    """Base command for the A3 plugin."""

    METADATA = CliCommandMetadata(
        id='base',
        logical_component='a3',
        description='Base command for a3 plugin',
        arguments=[
            {
                'accepts': [
                    '--help',
                    '-h',
                ],
                'description': 'Display help information',
            }
        ],
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log: callable = None

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """Check if the command is valid."""
        return True

    def run(self) -> CommandResponse:
        """Execute the command."""
        if len(self._request.command_args) == 1 and self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException()

        arg_list: Dict[str, str] = {}
        usage_list: Dict[str, str] = {'base': 'ontobdc a3 <argument> [flags/parameters]'}
        loader: PluginResource = CommandLoader('a3')
        for command in loader.get_all():
            if command.METADATA.id != 'base' and hasattr(command.METADATA, 'arguments') and command.METADATA.arguments:
                arg_key = ' | '.join(command.METADATA.arguments[0]['accepts'])
                arg_list[arg_key] = command.METADATA.arguments[0]['description']
                if 'usage' in command.METADATA.arguments[0]:
                    usage_list[command.METADATA.id] = command.METADATA.arguments[0]['usage']

        arg_list[' | '.join(self.METADATA.arguments[0]['accepts'])] = self.METADATA.arguments[0]['description']

        return HelpCommandResponse(
            title='A3 CLI Help',
            description='Display help information for the a3 component.',
            content={
                'Usage': usage_list,
                'Options': arg_list,
            }
        )
