from typing import Any, Dict, List, Type

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


class CliHelpCommand(CliCommandPort, LoggerAwarePort):
    """
    Command run by ``ontobdc --help`` / ``ontobdc -h``.

    Unlike :class:`CliBaseCommand`, which dumps the full nested flag tree,
    this lists one line per top-level command: what a newcomer needs to
    know which commands exist and which one to explore next with
    ``ontobdc <command> --help``.
    """

    HELP_FLAGS: List[str] = ["--help", "-h"]

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="help",
        logical_component="cli",
        description="Display a one-line summary of each top-level command.",
        depends_on=None,
        arguments=[
            {
                "accepts": HELP_FLAGS,
                "description": (
                    "Print one line per top-level command with what it is "
                    "for; run 'ontobdc <command> --help' for its details."
                ),
            },
        ],
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
        return len(args) == 1 and args[0] in CliHelpCommand.HELP_FLAGS

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        return CliHelpCommand.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        return HelpCommandResponse(
            title="OntoBDC Help",
            description=(
                "Command-line interface for OntoBDC. Run "
                "'ontobdc <command> --help' for details on a specific "
                "command."
            ),
            content={
                "Usage": "ontobdc <command> [flags/parameters]",
                "Commands": self._command_summaries(),
            },
        )

    def _command_summaries(self) -> Dict[str, str]:
        """
        Map each top-level command to the description of its entry command.

        The entry command of a component is the one whose id is ``base`` or
        the component name itself; when there is none, the first command
        found stands in for it. The ``cli`` component is skipped: its
        commands are the root flags, not a top-level command.
        """
        summaries: Dict[str, str] = {}
        components: List[str] = list(
            CommandTreeAdapter(
                logger=self._logger,
                root_package="ontobdc",
                executable="ontobdc",
            ).describe().keys()
        )
        component: str
        for component in components:
            if component == "cli":
                continue

            commands: List[Type[CliCommandPort]] = CommandLoader(
                component, self._logger,
            ).get_all()
            if not commands:
                continue

            entry_command: Type[CliCommandPort] = next(
                (
                    command for command in commands
                    if command.METADATA.id in ("base", component)
                ),
                commands[0],
            )
            summaries[component] = str(entry_command.METADATA.description or "").strip()

        return summaries
