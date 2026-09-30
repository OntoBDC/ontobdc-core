from typing import Any, List

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


class CliBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Command run by a bare ``ontobdc``, with no arguments at all.

    It prints the full command tree. ``--help``/``-h`` is a different
    command, :class:`CliHelpCommand`, with its own output.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="base",
        logical_component="cli",
        description=(
            "Print the tree of every command registered in the active "
            "executable, with aliases, optionality markers and descriptions "
            "for each argument."
        ),
        depends_on=None,
        arguments=[],
    )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return not args

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        return CliBaseCommand.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        command_tree: str = CommandTreeAdapter(
            logger=self._logger,
            root_package="ontobdc",
            executable="ontobdc",
        ).render()

        return HelpCommandResponse(
            title="OntoBDC Commands",
            description="Available commands and options.",
            content={
                "Usage": "ontobdc <command> [flags/parameters]",
                "Commands": command_tree,
            },
        )
