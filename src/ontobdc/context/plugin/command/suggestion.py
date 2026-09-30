from typing import Any, ClassVar, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.context.plugin.machine.file_meaning_suggestion.port import (
    FileMeaningSuggestionStateTransitionHandlerPort,
)
from ontobdc.context.plugin.machine.file_meaning_suggestion.machine import (
    FileMeaningSuggestionStateTransitionHandler,
)


class ContextSuggestionCommand(CliCommandPort, LoggerAwarePort):
    """
    Command for suggesting the ontology meaning of every file a selected
    container holds, from the paths its RO-Crate states.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="context_suggestion",
        logical_component="context",
        description=(
            "Suggest the meaning of every file a container holds, from "
            "the paths its RO-Crate states."
        ),
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select which container to run the file meaning "
                    "suggestion pipeline against, by storage identifier "
                    "or filesystem path. When omitted, the container is "
                    "resolved from the current working directory. The "
                    "pipeline suggests ontology classes for every file "
                    "the container's RO-Crate declares."
                ),
            },
        ],
    )

    SUGGESTION_FLAG: ClassVar[str] = "--suggestion"
    CONTAINER_FLAG: ClassVar[str] = "--container"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the context suggestion command at the CLI routing stage.
        """
        if not args or args[0] != "context":
            return False

        return ContextSuggestionCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        container_path: Any = self._request.context.get_parameter_value(
            "container_path"
        )

        return isinstance(container_path, str) and bool(container_path.strip())

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --suggestion with an optional
        --container <id-or-path>, in either order.

        The selector and the action are independent flags, not positions --
        which one a user writes first is not part of the command's meaning.
        """
        if ContextSuggestionCommand.SUGGESTION_FLAG not in scoped_args:
            return False

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContextSuggestionCommand.SUGGESTION_FLAG)
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ContextSuggestionCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> CommandResponse:
        """
        Drive the selected container through the file meaning suggestion
        pipeline.
        """
        handler: FileMeaningSuggestionStateTransitionHandlerPort = (
            FileMeaningSuggestionStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )

        return handler.execute()
