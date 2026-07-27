
from pathlib import Path
from typing import List, Optional
from ontobdc.shared.facade.response.command import CommandResponse
from ontobdc.shared.facade.request.command import CliCommandRequest
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.storage.adapter.machine import DatasetCreateStateTransitionHandler
from ontobdc.storage.plugin.check.is_container_id_registered.check import (
    get_registered_container_location,
    main as check_container_id_registered,
)
from ontobdc.shared.facade.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.storage.domain.port.machine import DatasetCreateStateTransitionHandlerPort


class DatasetCreateCommand(CliCommandPort):
    """
    Command for creating a new dataset inside a storage container.
    """

    METADATA = CliCommandMetadata(
        id="ds_create",
        logical_component="storage",
        description="Create a new dataset inside a local storage container.",
        arguments=[
            {
                "accepts": ["--container-id"],
                "valued": True,
                "description": "Select the target storage container identifier.",
                "usage": "ontobdc storage --container-id <container_id> --create <path>",
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "description": "Create a new dataset at the given path inside the selected container.",
                "usage": "ontobdc storage --container-id <container_id> --create <path>",
            },
        ],
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage dataset creation command at the CLI routing stage.
        """
        return (
            len(args) > 4
            and args[0] == "storage"
            and "--container-id" in args
            and "--create" in args
        )

    def __init__(self, request: CliCommandRequest):
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        command_args: List[str] = self._request.command_args

        if not (
            len(command_args) == 4
            and command_args[0] == "--container-id"
            and command_args[2] == "--create"
        ):
            return False

        container_id: str = command_args[1].strip()
        if not container_id:
            return False

        if check_container_id_registered(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        ) != 0:
            raise CliCommandArgumentException(f"Invalid container-id: {container_id}")

        dataset_path: str = command_args[3].strip()
        if not dataset_path:
            return False

        resolved_dataset_path: Optional[Path] = self._resolve_dataset_path(
            container_id=container_id,
            dataset_path=dataset_path,
        )
        if resolved_dataset_path is None:
            raise CliCommandArgumentException(
                f"Invalid dataset_path: {dataset_path}. It must be a single child directory inside container {container_id}."
            )

        self._request.context.delete_parameter("container_path")
        self._request.context.set_parameter_value("container_id", container_id)
        self._request.context.set_parameter_value("dataset_path", str(resolved_dataset_path))

        return True

    def _resolve_dataset_path(
        self,
        container_id: str,
        dataset_path: str,
    ) -> Optional[Path]:
        container_path: Optional[Path] = get_registered_container_location(
            container_id=container_id,
            root_path=str(self._request.context.root_path),
        )
        if container_path is None:
            return None

        dataset_candidate: Path = Path(dataset_path).expanduser()
        root_path: Path = Path(self._request.context.root_path).expanduser().resolve()
        candidate_paths: List[Path] = []
        if dataset_candidate.is_absolute():
            candidate_paths.append(dataset_candidate.resolve())
        else:
            candidate_paths.append((root_path / dataset_candidate).resolve())
            candidate_paths.append((container_path / dataset_candidate).resolve())

        unique_candidates: List[Path] = []
        for candidate_path in candidate_paths:
            if candidate_path not in unique_candidates:
                unique_candidates.append(candidate_path)

        for resolved_dataset_path in unique_candidates:
            if resolved_dataset_path == container_path:
                continue

            try:
                relative_dataset_path: Path = resolved_dataset_path.relative_to(container_path)
            except ValueError:
                continue

            if len(relative_dataset_path.parts) != 1:
                continue

            if resolved_dataset_path.exists() and not resolved_dataset_path.is_dir():
                continue

            return resolved_dataset_path

        return None

    def run(self) -> CommandResponse:
        """
        Execute the command to create a new local dataset.
        """
        handler: DatasetCreateStateTransitionHandlerPort = DatasetCreateStateTransitionHandler(
            context=self._request.context,
        )

        return handler.execute()
