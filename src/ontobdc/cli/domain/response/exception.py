from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.suggestion import CommandSuggestionPort
from ontobdc.cli.domain.response.command import ExceptionCommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException


class ExceptionResponseBuilder:
    """
    Turn a failure with no builder of its own into a response.

    Every uncaught failure reaches the user through the same response
    model, so a type nobody registered a builder for still gets rendered
    rather than crashing the error path itself.

    The suggestion port is part of the builder contract the loader
    constructs against. A failure that is not about the arguments has
    nothing to suggest, so this builder takes it and keeps none of it.
    """

    def __init__(
        self,
        exception: Exception,
        suggestion: CommandSuggestionPort,
    ) -> None:
        self._exception: Exception = exception

    def build(self) -> ExceptionCommandResponse:
        response: ExceptionCommandResponse = ExceptionCommandResponse(
            description=f"Command execution failed as <{type(self._exception).__name__}>.",
            content={"error": str(self._exception)},
        )

        return response


class CliCommandArgumentExceptionResponseBuilder:
    """
    Turn a rejected invocation into the response the user reads.

    Beyond naming the failure, the builder asks the suggestion port which
    registered commands come closest to what was typed, so a mistyped flag
    is answered with the forms the CLI really accepts instead of a bare
    refusal. Nothing is suggested when the exception carries no arguments —
    a command that refused a *value* was itself the right command — nor
    when no registered form is close enough to be worth showing.
    """

    SUGGESTION_KEY: str = "did you mean"

    def __init__(
        self,
        exception: CliCommandArgumentException,
        suggestion: CommandSuggestionPort,
    ) -> None:
        self._exception: CliCommandArgumentException = exception
        self._suggestion: CommandSuggestionPort = suggestion

    def build(self) -> ExceptionCommandResponse:
        content: Dict[str, Any] = {"error": str(self._exception)}

        suggested_commands: List[str] = self._suggested_commands()
        if suggested_commands:
            content[self.SUGGESTION_KEY] = suggested_commands

        response: ExceptionCommandResponse = ExceptionCommandResponse(
            description=f"Command execution failed as <{self._exception.IDENTIFIER} ({type(self._exception).__name__})>.",
            content=content,
        )

        return response

    def _suggested_commands(self) -> List[str]:
        """
        Return the registered commands closest to the rejected arguments.
        """
        command_args: Optional[List[str]] = self._exception.command_args
        if not command_args:
            return []

        return self._suggestion.suggest(command_args)
