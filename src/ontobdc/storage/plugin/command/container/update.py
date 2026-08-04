from pathlib import Path
from typing import List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage.adapter.machine import ContainerUpdateStateTransitionHandler
from ontobdc.storage.domain.port.machine import (
    ContainerUpdateStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
)


class StorageUpdateCommand(CliCommandPort):
    """Update an existing registered container through its state machine."""

    METADATA = CliCommandMetadata(
        id="container_update",
        logical_component="storage",
        description=(
            "Run the standard cleanup and update process for a registered "
            "storage container."
        ),
        arguments=[
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": (
                    "Select the registered container identifier. When omitted, "
                    "resolve the container from the current working directory."
                ),
                "usage": (
                    "ontobdc storage --update | "
                    "ontobdc storage --container-id <container_id> --update"
                ),
            },
            {
                "accepts": ["--update"],
                "description": (
                    "Clean the container, update its metadata, and update its "
                    "existing HTML view."
                ),
                "usage": (
                    "ontobdc storage --update | "
                    "ontobdc storage --container-id <container_id> --update"
                ),
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if args == ["storage", "--update"]:
            return True

        return (
            len(args) == 4
            and args[0] == "storage"
            and args[1] in {"--container-id", "--container"}
            and args[3] == "--update"
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        command_args: List[str] = self._request.command_args
        requested_container_id: Optional[str] = None

        if command_args == ["--update"]:
            context_container_id: Optional[object] = (
                self._request.context.get_parameter_value("container_id")
            )
            if context_container_id is not None:
                normalized_context_container_id: str = str(
                    context_container_id
                ).strip()
                requested_container_id = (
                    normalized_context_container_id or None
                )

            if requested_container_id is None:
                raise CliCommandArgumentException(
                    "Unable to resolve the current container from the working "
                    "directory. Run the command inside a registered container "
                    "or provide --container-id <container_id>."
                )

        elif (
            len(command_args) == 3
            and command_args[0] in {"--container-id", "--container"}
            and command_args[2] == "--update"
        ):
            normalized_requested_container_id: str = command_args[1].strip()
            if not normalized_requested_container_id:
                return False
            requested_container_id = normalized_requested_container_id

        else:
            return False

        resolved_container = self._resolve_registered_container(
            requested_container_id
        )
        if resolved_container is None:
            raise CliCommandArgumentException(
                f"Container is not registered: {requested_container_id}"
            )

        canonical_container_id, container_path = resolved_container
        self._request.context.delete_parameter("container")
        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value(
            "container_id",
            canonical_container_id,
        )
        self._request.context.set_parameter_value(
            "container_path",
            str(container_path),
        )
        return True

    def run(self) -> CommandResponse:
        handler: ContainerUpdateStateTransitionHandlerPort = (
            ContainerUpdateStateTransitionHandler(
                context=self._request.context,
            )
        )
        return handler.execute()

    def _resolve_registered_container(
        self,
        requested_container_id: str,
    ) -> Optional[tuple[str, Path]]:
        candidates: List[str] = [requested_container_id]
        if not requested_container_id.startswith("urn:"):
            candidates.append(
                f"urn:ontobdc:storage/local/{requested_container_id}"
            )

        root_path: str = str(self._request.context.root_path)
        for candidate in candidates:
            container_path: Optional[Path] = get_registered_container_location(
                container_id=candidate,
                root_path=root_path,
            )
            if container_path is not None:
                return candidate, container_path

        return None
