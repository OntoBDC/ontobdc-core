
from pathlib import Path
from typing import List, Any

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.adapter.machine import CliInitStateTransitionHandler
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError


class CliInitCommand(CliCommandPort):
    """
    Command to initialize the ontobdc configuration in a project.
    """
    METADATA = CliCommandMetadata(
        id="init",
        logical_component="cli",
        description="Initialize ontobdc in the current directory.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "init",
                ],
                "description": "Initialize ontobdc in the current directory.",
            },
        ],
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
        """
        Check if the command accepts the given arguments.
        Returns True if the command accepts the arguments, False otherwise.
        """
        return len(args) == 1 and args[0] == "init"

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        try:
            if isinstance(self._request.context.root_path, Path):
                return False
        except ProjectRootDirectoryNotSetError:
            pass

        return True

    def run(self) -> CommandResponse:
        """
        Execute the command to initialize the ontobdc environment.
        """
        handler: CliInitStateTransitionHandler = CliInitStateTransitionHandler(
            context=self._request.context,
            logger=self._logger,
        )

        return handler.execute()
