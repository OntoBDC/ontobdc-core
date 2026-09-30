from typing import Any, ClassVar, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.machine.container_refresh.machine import (
    ContainerRefreshStateTransitionHandler,
)
from ontobdc.container.plugin.machine.container_refresh.port import (
    ContainerRefreshStateTransitionHandlerPort,
)


class ContainerRefreshCommand(CliCommandPort, LoggerAwarePort):
    """
    Command for bringing a registered container back in line with its files.

    Refreshing reads what the container actually holds and rewrites what
    describes it: the datasets it indexes, the datapackage that lists its
    resources, and the RO-Crate. It changes no data of its own — a user who
    wants to write values into the container metadata uses
    ``container update --from`` instead.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_refresh",
        logical_component="container",
        description="Refresh a registered container from the files it holds.",
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select which container to refresh, by storage "
                    "identifier or filesystem path. When omitted, the "
                    "container is resolved from the current working "
                    "directory. Refreshing rebuilds datasets, datapackage "
                    "and RO-Crate from the files the container actually "
                    "holds; it never writes values into metadata fields."
                ),
            },
        ],
    )

    REFRESH_FLAG: ClassVar[str] = "--refresh"
    CONTAINER_FLAG: ClassVar[str] = "--container"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container refresh command at the CLI routing stage.
        """
        if not args or args[0] != "container":
            return False

        return ContainerRefreshCommand._matches(args[1:])

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
        Report whether these scoped args are --refresh with an optional
        --container <id-or-path>, in either order.

        The selector and the action are independent flags, not positions --
        a user (or an automated caller filling in --container on their
        behalf) should be free to write either one first.
        """
        if ContainerRefreshCommand.REFRESH_FLAG not in scoped_args:
            return False

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContainerRefreshCommand.REFRESH_FLAG)
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ContainerRefreshCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> CommandResponse:
        """
        Drive the selected container through the refresh pipeline.
        """
        handler: ContainerRefreshStateTransitionHandlerPort = (
            ContainerRefreshStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )

        return handler.execute()
