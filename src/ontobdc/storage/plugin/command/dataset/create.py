from pathlib import Path
from typing import List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.storage.adapter.machine import DatasetCreateStateTransitionHandler
from ontobdc.storage.domain.port.machine import (
    DatasetCreateStateTransitionHandlerPort,
)
from ontobdc.storage.plugin.parameter.container import ContainerIdStrategy


class DatasetCreateCommand(CliCommandPort):
    """Create a new dataset inside a resolved storage container."""

    METADATA = CliCommandMetadata(
        id="ds_create",
        logical_component="storage",
        description="Create a new dataset inside a local storage container.",
        arguments=[
            {
                "accepts": ["--container-id", "--container"],
                "valued": True,
                "description": (
                    "Select a registered container by ID, or use --container "
                    "with either an ID or filesystem path."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> "
                    "--create <path>"
                ),
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": (
                    "Create a new dataset at the given path inside the "
                    "selected container."
                ),
                "usage": (
                    "ontobdc storage --container <id-or-path> "
                    "--create <path>"
                ),
            },
        ],
    )

    _CONTAINER_FLAGS = {"--container-id", "--container"}

    @staticmethod
    def accepts(args: List[str]) -> bool:
        return (
            len(args) == 5
            and args[0] == "storage"
            and args[1] in DatasetCreateCommand._CONTAINER_FLAGS
            and bool(str(args[2]).strip())
            and args[3] == "--create"
            and bool(str(args[4]).strip())
        )

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        command_args = self._request.command_args
        if not (
            len(command_args) == 4
            and command_args[0] in self._CONTAINER_FLAGS
            and command_args[2] == "--create"
        ):
            return False

        selector_flag = command_args[0]
        selector_value = str(command_args[1] or "").strip()
        dataset_path = str(command_args[3] or "").strip()
        if not selector_value or not dataset_path:
            return False

        context = self._request.context
        for parameter_name in (
            "container",
            "container_id",
            "container_path",
            "dataset_path",
        ):
            context.delete_parameter(parameter_name)

        selector_parameter = selector_flag.removeprefix("--").replace("-", "_")
        context.set_parameter_value(selector_parameter, selector_value)
        ContainerIdStrategy().execute(context)

        resolved_container_id = str(
            context.get_parameter_value("container_id") or ""
        ).strip()
        resolved_container_path_value = str(
            context.get_parameter_value("container_path") or ""
        ).strip()
        if not resolved_container_id or not resolved_container_path_value:
            raise CliCommandArgumentException(
                f"Invalid container selector: {selector_value}"
            )

        resolved_dataset_path = self._resolve_dataset_path(
            container_path=Path(resolved_container_path_value),
            dataset_path=dataset_path,
        )
        if resolved_dataset_path is None:
            raise CliCommandArgumentException(
                f"Invalid dataset_path: {dataset_path}. It must be a single "
                f"child directory inside container {resolved_container_id}."
            )

        context.set_parameter_value("dataset_path", str(resolved_dataset_path))
        return True

    @staticmethod
    def _resolve_dataset_path(
        container_path: Path,
        dataset_path: str,
    ) -> Optional[Path]:
        resolved_container_path = container_path.expanduser().resolve()
        dataset_candidate = Path(dataset_path).expanduser()
        resolved_dataset_path = (
            dataset_candidate.resolve()
            if dataset_candidate.is_absolute()
            else (resolved_container_path / dataset_candidate).resolve()
        )

        if resolved_dataset_path == resolved_container_path:
            return None

        try:
            relative_dataset_path = resolved_dataset_path.relative_to(
                resolved_container_path
            )
        except ValueError:
            return None

        if len(relative_dataset_path.parts) != 1:
            return None
        if (
            resolved_dataset_path.exists()
            and not resolved_dataset_path.is_dir()
        ):
            return None
        return resolved_dataset_path

    def run(self) -> CommandResponse:
        handler: DatasetCreateStateTransitionHandlerPort = (
            DatasetCreateStateTransitionHandler(
                context=self._request.context,
            )
        )
        return handler.execute()
