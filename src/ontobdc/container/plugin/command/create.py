from typing import List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.plugin.machine.container_create.machine import ContainerCreateStateTransitionHandler
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.machine.container_create.port import (
    ContainerCreateStateTransitionHandlerPort,
)


class ContainerCreateCommand(CliCommandPort):
    """
    Command for creating a new local container at the given path.

    Routing, argument validation and context binding are in place. The
    creation pipeline itself — the container create state machine and the
    capability engine it drives — has not been restored yet, so ``run``
    reports that instead of performing the creation.
    """
    METADATA = CliCommandMetadata(
        id="ct_create",
        logical_component="container",
        description="Create a new local container at the given path.",
        arguments=[
            {
                "accepts": [
                    "--create",
                ],
                "valued": True,
                "description": (
                    "Filesystem path where the new local container will "
                    "be created. The creation pipeline writes the "
                    "container metadata, initializes its datasets folder "
                    "and registers the container in the storage index."
                ),
            },
        ],
    )

    _PENDING_REASON: str = (
        "The container creation pipeline is not available in this build: "
        "the create state machine and the capability engine it drives have "
        "not been restored yet."
    )
    # Kept short on purpose: the widget adapter renders this value inside a
    # fenced block, which the terminal surface prints verbatim, without
    # wrapping it to the frame width.
    _PENDING_ERROR: str = "Container creation pipeline not restored."

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container creation command at the CLI routing stage.
        """
        return len(args) > 2 and args[0] == "container" and args[1] == "--create"

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

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
        self._request.context.set_parameter_value(
            "container_path",
            self._request.command_args[1],
        )

        return True

    def run(self) -> CommandResponse:
        """
        Report that the creation pipeline is not available yet.
        """
        handler: ContainerCreateStateTransitionHandlerPort = ContainerCreateStateTransitionHandler(
            context=self._request.context,
        )

        return handler.execute()
