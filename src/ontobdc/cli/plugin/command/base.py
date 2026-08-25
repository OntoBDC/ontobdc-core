from typing import Any, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse, HelpCommandResponse


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
