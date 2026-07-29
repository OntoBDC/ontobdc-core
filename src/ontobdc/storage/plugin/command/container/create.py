
from typing import List
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.storage.adapter.machine import ContainerCreateStateTransitionHandler
from ontobdc.storage.domain.port.machine import ContainerCreateStateTransitionHandlerPort


class StorageCreateCommand(CliCommandPort):
    """
    Command for creating a new local storage container at the given path.
    """
    METADATA = CliCommandMetadata(
        id="ct_create",
        logical_component="storage",
        description="Create a new local storage container at the given path.",
        arguments=[
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": "Create a new local storage container at the given path.",
                "usage": "ontobdc storage --create <path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage container creation command at the CLI routing stage.
        """
        return len(args) > 2 and args[0] == "storage" and args[1] == "--create"

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request
        # self._logger: LogRepositoryPort = NullLogRepository()
        #self._log_strategy: Any = None

    #@property
    #def log_strategy(self) -> Any:
    #    return self._log_strategy

    #def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
    #    self._log_strategy = log_strategy
    #    self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not (
            len(self._request.command_args) == 2
            and self._request.command_args[0] == "--create"
        ):
            return False

        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value("container_path", self._request.command_args[1])

        return True

    def run(self) -> CommandResponse:
        """
        Execute the command to create a new local container.
        """
        handler: ContainerCreateStateTransitionHandlerPort = ContainerCreateStateTransitionHandler(
            context=self._request.context,
            # logger=self._logger,
        )

        return handler.execute()
