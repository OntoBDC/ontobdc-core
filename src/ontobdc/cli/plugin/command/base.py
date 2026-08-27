from typing import Any, Dict, List, Type

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse
from ontobdc.shared.adapter.loader import CommandLoader


class CliBaseCommand(CliCommandPort, LoggerAwarePort):
    """Base command shown by ``ontobdc`` with no arguments."""

    METADATA = CliCommandMetadata(
        id="base",
        logical_component="cli",
        description="Base CLI command handler.",
        depends_on=None,
    )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args:
            return True

        return len(args) == 1 and args[0] in ["--help", "-h"]

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        return self.__class__.accepts(self._request.command_args)

    def run(self) -> CommandResponse:
        if (
            len(self._request.command_args) > 1
            and self._request.command_args[0] not in ["--help", "-h"]
        ):
            raise CliCommandArgumentException()

        if not self._request.command_args:
            command_tree: str = CommandTreeAdapter(
                logger=self._logger,
            ).render()

            return HelpCommandResponse(
                title="OntoBDC Commands",
                description="Available commands and options.",
                content={
                    "Usage": "ontobdc <command> [flags/parameters]",
                    "Commands": command_tree,
                },
            )

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
        """One line per top-level command, not the full nested flag tree.

        ``ontobdc --help`` used to dump :class:`CommandTreeAdapter`'s deep
        ``├──``/``└──`` argument tree -- every flag combination for every
        subcommand -- which is the right tool for exploring one component
        in depth (see ``ontobdc storage --help``) but the wrong first
        screen: a newcomer just needs to know which top-level commands
        exist, what each one is for, and one concrete example to copy.
        """
        summaries: Dict[str, str] = {}
        tree_adapter: CommandTreeAdapter = CommandTreeAdapter(
            logger=self._logger,
        )
        component: str
        for component in tree_adapter._discover_logical_components():
            if component == "cli":
                continue
            try:
                commands: List[Type[CliCommandPort]] = CommandLoader(
                    component, self._logger,
                ).get_all()
            except Exception:
                continue
            if not commands:
                continue
            chosen: Type[CliCommandPort] = next(
                (
                    command for command in commands
                    if command.METADATA.id in ("base", component)
                ),
                commands[0],
            )
            description: str = str(chosen.METADATA.description or "").strip()
            example: str = self._first_usage_example(commands)
            summaries[component] = (
                f"{description}\nExample: {example}" if example else description
            )
        return summaries

    @staticmethod
    def _first_usage_example(commands: List[Type[CliCommandPort]]) -> str:
        """The first ``usage`` string declared by any command's arguments.

        Individual commands already carry a concrete ``usage`` string per
        argument (see e.g. ``StorageBaseCommand``, ``ContainerViewCommand``,
        ``ContextEntityCommand``) -- this just surfaces the first one found
        for the component, the same source ``StorageHelpCommand`` reads
        from, instead of inventing a new example.
        """
        for command in commands:
            arguments: Any = getattr(command.METADATA, "arguments", None) or []
            for argument in arguments:
                usage: str = str(argument.get("usage") or "").strip()
                if usage:
                    return usage
        return ""
