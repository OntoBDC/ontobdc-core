from typing import List, Optional


class CliCommandArgumentException(Exception):
    """
    Exception for invalid CLI command arguments.

    Carries the arguments that were rejected when the failure is about the
    arguments themselves — no command matched them, or the command that did
    refused their shape. A command that rejects a *value* it was given
    raises this without them, because there is nothing to suggest: the
    command was right, the value was not.
    """

    IDENTIFIER = "org.ontobdc.cli.domain.exception.command.argument"
    TITLE = "Invalid Command Arguments"

    def __init__(
        self,
        message: str = "Invalid command arguments.",
        command_args: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.command_args: Optional[List[str]] = command_args
