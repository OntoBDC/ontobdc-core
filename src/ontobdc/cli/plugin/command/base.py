
from typing import List

from ontobdc.cli.adapter.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.port.command import CliCommandMetadata, CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


class CliBaseCommand(CliCommandPort):
    """
    Helper class for base command loading.
    """
    METADATA = CliCommandMetadata(
        id="base",
        logical_component="cli",
        description="Base CLI command handler.",
        depends_on=None,
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._print_log : callable = None

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        if not args:
            return True

        return len(args) == 0

    def set_print_log(self, print_log: callable):
        self._print_log = print_log

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self.__class__.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        """
        Execute the command.
        """
        if len(self._request.command_args) > 1 and self._request.command_args[0] not in ['--help', '-h']:
            raise CliCommandArgumentException()

        command_list = {}
        from ontobdc.shared.adapter.plugin import CommandLoader

        # Discover all logical components dynamically
        dummy_loader = CommandLoader("")
        logical_components = sorted(list(set(
            pkg.split('.')[1] for pkg in dummy_loader._list_plugin_folder("command")
        )))

        for component in logical_components:
            loader = CommandLoader(component, self._print_log)
            for cmd_class in loader.get_all():
                if not isinstance(cmd_class, type):
                    continue
                if cmd_class.METADATA.id == 'base':
                    continue

                # Recupera o comando principal diretamente do accepts definido nos argumentos
                main_flag = ""
                if cmd_class.METADATA.arguments and len(cmd_class.METADATA.arguments) > 0:
                    accepts = cmd_class.METADATA.arguments[0].get("accepts", [])
                    if accepts:
                        main_flag = accepts[0]
                
                # Se não houver argumento mapeado (fallback extremo), pula ou usa o id
                if not main_flag:
                    continue

                if component == 'cli':
                    cmd_name = f"{main_flag}"
                else:
                    cmd_name = f"{component}-{main_flag.strip('-')}"

                command_list[cmd_name] = {
                            "id": cmd_class.METADATA.id,
                            "logical_component": component,
                            "accepts": accepts,
                            "description": cmd_class.METADATA.description
                        }

        return HelpCommandResponse(
            title="CLI Help",
            description="Display help information for the CLI.",
            content={
                "Usage": ["ontobdc <command> [flags/parameters]"],
                "Commands": command_list,
            }
        )
        
