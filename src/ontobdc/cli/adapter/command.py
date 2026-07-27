from typing import Dict, List, Optional, Type
from ontobdc.cli.adapter.context import CliContextAdapter
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.health import CliCommandHealthPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.shared.adapter.loader import CommandLoader
from ontobdc.shared.domain.port.loader import CommandLoaderPort
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.domain.exception.config import ProjectRootDirectoryNotSetError
from ontobdc.cli.adapter.health import CliBootstrapHealthAdapter, NoHealthCheckAdapter

__all__ = ["CliCommandMetadata", "CliCommandRunAdapter"]


class CliCommandRunAdapter:
    """
    Small adapter layer for future command-style CLI execution.

    The current `ontobdc.cli.__init__.py` still contains the legacy dispatch
    flow, so this adapter must be safe to call before that logic runs.
    """
    @staticmethod
    def check(args: List[str], logger: LogRepositoryPort, level: int = None) -> bool:
        """
        Check if the system is in a valid state to execute the command.
        """
        health_adapter_by_level: Dict[int, Type[CliCommandHealthPort]] = {
            0: NoHealthCheckAdapter,
            1: CliBootstrapHealthAdapter,
        }

        if level is None:
            level = len(health_adapter_by_level) - 1

        health_adapter_class: Optional[Type[CliCommandHealthPort]] = health_adapter_by_level.get(level)
        if health_adapter_class is None:
            raise CliCommandArgumentException(f"Unsupported health check level: {level}")

        health_adapter: CliCommandHealthPort = health_adapter_class()

        return health_adapter.check(args, logger)

    @classmethod
    def make(
        cls,
        args: List[str],
        logger: LogRepositoryPort,
        check_level: int = 1,
        loader_class: Optional[Type[CommandLoaderPort]] = None,
    ) -> CliCommandPort:
        """
        Create a command adapter from raw CLI arguments.
        """
        is_valid: bool = False
        if loader_class is None:
            loader_class = CommandLoader

        try:
            is_valid = cls.check(args, logger, check_level)
        except ProjectRootDirectoryNotSetError:
            is_valid = cls.check(args, logger, 0)

        if not is_valid:
            raise CliCommandArgumentException(f"Invalid command arguments: {args}")

        candidate_list: Dict[str, Type[CliCommandPort]] = {}

        clean_args: List[str] = args
        command_classes: List[Type[CliCommandPort]] = []
        try:
            loader: CommandLoaderPort = loader_class('cli', logger)
            command_classes = loader.get_all()
            if args:
                if not args[0].startswith("-"):
                    scoped_loader: CommandLoaderPort = loader_class(args[0], logger)
                    scoped_command_classes: List[Type[CliCommandPort]] = scoped_loader.get_all()
                    if len(scoped_command_classes) > 0:
                        command_classes = scoped_command_classes
                        clean_args = args[1:]

            for command_class in command_classes:
                if isinstance(command_class, type):
                    if command_class.accepts(args):
                        candidate_list[command_class.METADATA.id] = command_class

        except Exception as e:
            logger.log_error(f"Invalid command arguments: {args} - {e}")

        if len(candidate_list) == 0:
            raise CliCommandArgumentException(f"Invalid command arguments: {args}")

        if len(candidate_list) > 1:
            raise CliCommandArgumentException(f"Invalid command arguments: {args} - Multiple commands match {args}")

        command_class: Type[CliCommandPort] = next(iter(candidate_list.values()))
        try:
            request: CliCommandRequest = CliCommandRequest(
                logical_component=command_class.METADATA.logical_component,
                component_action=command_class.METADATA.id,
                command_args=clean_args,
                context=CliContextAdapter(clean_args),
            )
            command: CliCommandPort = command_class(request)
            if not command.check():
                raise CliCommandArgumentException(f"Invalid command arguments: {args}")

            return command
        except ProjectRootDirectoryNotSetError:
            raise
