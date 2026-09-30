from typing import Any, ClassVar, Dict, List, Tuple, Type

from ontobdc.cli.adapter.tree import CommandTreeAdapter
from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import HelpCommandResponse


class AnnotateBaseCommand(CliCommandPort, LoggerAwarePort):
    """
    Command shown by ``ontobdc annotate`` with no arguments.

    Annotating always names a file, so there is nothing this component can do
    with no arguments other than say what it answers to.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="base",
        logical_component="annotate",
        description="Base annotate command handler.",
        depends_on=None,
    )

    COMPONENT: ClassVar[str] = "annotate"
    EXECUTABLE: ClassVar[str] = "ontobdc"
    HELP_FLAGS: ClassVar[List[str]] = ["--help", "-h"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the bare component and its help flags at the routing stage.
        """
        if not args or args[0] != AnnotateBaseCommand.COMPONENT:
            return False

        return len(args) == 1 or (
            len(args) == 2 and args[1] in AnnotateBaseCommand.HELP_FLAGS
        )

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
        command_args: List[str] = self._request.command_args

        return not command_args or (
            len(command_args) == 1 and command_args[0] in self.HELP_FLAGS
        )

    def run(self) -> HelpCommandResponse:
        """
        List what the annotate component answers to.
        """
        # Scoped to this component on purpose: a user who typed the
        # component name is asking what it answers to, not what the whole
        # executable offers.
        component_commands: List[Tuple[str, Type[CliCommandPort]]] = [
            (self.COMPONENT, command_class)
            for command_class in CommandLoader(
                self.COMPONENT,
                self._logger,
            ).get_all()
        ]
        command_tree: str = CommandTreeAdapter(
            logger=self._logger,
            root_package="ontobdc",
            executable=self.EXECUTABLE,
            command_classes=component_commands,
        ).render()

        content: Dict[str, str] = {
            "Usage": f"{self.EXECUTABLE} {self.COMPONENT} [flags/parameters]",
            "Commands": command_tree,
        }

        return HelpCommandResponse(
            title="Annotate Commands",
            description="Available annotate commands and options.",
            content=content,
        )
