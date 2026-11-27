from typing import Any, ClassVar, List

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.plugin.machine.init_addon.machine import CliInitAddonStateTransitionHandler
from ontobdc.cli.plugin.machine.init_addon.request import CliInitAddonRequest


class CliInitAddonCommand(CliCommandPort, LoggerAwarePort):
    """
    Command that adds an addon: ``ontobdc init --addon <folder or address of the addon>``. The addition is a machine of its
    own, which locates the folder of the addon and adds it.
    """

    COMPONENT: ClassVar[str] = "init"
    ADDON_FLAG: ClassVar[str] = "--addon"

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="init_addon",
        logical_component="cli",
        description="Add an addon, from its folder or from the address of its folder in a repository of GitHub.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--addon"],
                "valued": True,
                "required": True,
                "parameter": CliInitAddonRequest.SOURCE_KEY,
                "description": (
                    "The folder of the addon on this machine, or the address of its folder in a repository of GitHub "
                    "(https://github.com/<owner>/<repo>/tree/<ref>/<folder>)."
                ),
                "type": "str",
                "usage": "ontobdc init --addon <addon folder or address>",
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
        return (
            len(args) == 3
            and args[0] == CliInitAddonCommand.COMPONENT
            and args[1] == CliInitAddonCommand.ADDON_FLAG
            and bool(args[2].strip())
            and not args[2].startswith("--")
        )

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        if not self.accepts(self._request.command_args):
            raise CliCommandArgumentException("Usage: ontobdc init --addon <addon folder or address>")

        return True

    def run(self) -> CommandResponse:
        return CliInitAddonStateTransitionHandler(context=self._request.context, logger=self._logger).execute()
