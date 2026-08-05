from pathlib import Path
from typing import List

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage.adapter.attach_machine import (
    ContainerAttachStateTransitionHandler,
)
from ontobdc.storage.adapter.attachment import (
    ATTACH_COMPLETED_PARAMETER,
    ATTACH_ERROR_PARAMETER,
    ATTACH_PLAN_PARAMETER,
)


class StorageAttachCommand(CliCommandPort):
    """Attach an imported storage container to the current project root."""

    METADATA = CliCommandMetadata(
        id="container_attach",
        logical_component="storage",
        description=(
            "Reconcile an imported container identity, datasets, storage index, "
            "and execution context with the current project root."
        ),
        arguments=[
            {
                "accepts": ["--container-path"],
                "valued": True,
                "description": (
                    "Filesystem path of the imported container to attach."
                ),
                "usage": (
                    "ontobdc storage --container-path <cp> --attach"
                ),
            },
            {
                "accepts": ["--attach"],
                "description": (
                    "Attach the imported container to the current local storage."
                ),
                "usage": (
                    "ontobdc storage --container-path <cp> --attach"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 4
            and args[0] == "storage"
            and args[1] == "--container-path"
            and bool(str(args[2]).strip())
            and args[3] == "--attach"
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        command_args = self._request.command_args
        if not (
            len(command_args) == 3
            and command_args[0] == "--container-path"
            and command_args[2] == "--attach"
        ):
            return False

        raw_path = str(command_args[1] or "").strip()
        if not raw_path:
            return False
        try:
            container_path = Path(raw_path).expanduser().resolve()
        except (OSError, RuntimeError, TypeError, ValueError):
            return False
        if not container_path.is_dir():
            return False

        context = self._request.context
        context.set_parameter_value("container_path", str(container_path))
        for parameter_name in (
            ATTACH_PLAN_PARAMETER,
            ATTACH_COMPLETED_PARAMETER,
            ATTACH_ERROR_PARAMETER,
        ):
            context.delete_parameter(parameter_name)
        return True

    def run(self) -> CommandResponse:
        handler = ContainerAttachStateTransitionHandler(
            context=self._request.context,
        )
        return handler.execute()
