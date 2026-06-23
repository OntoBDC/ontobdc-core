


class CliCommandArgumentException(Exception):
    """
    Exception for invalid CLI command arguments.
    """

    IDENTIFIER = "org.ontobdc.cli.exception.command.argument"
    TITLE = "Invalid Command Arguments"

    def __init__(self, message: str = "Invalid command arguments."):
        super().__init__(message)

