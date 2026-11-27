import shutil
from pathlib import Path
from typing import ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.dataset import RegisteredDatasets


class ContainerDeleteDatasetCommand(CliCommandPort):
    """
    Command for deleting a dataset of a container: ``ontobdc container --delete-dataset <name> [--container <id-or-path>]
    [--purge]``.

    Without ``--purge`` the dataset is only taken out of the register of the container, and everything it has stays on
    the disk. With ``--purge`` its folder is deleted too.
    """

    METADATA = CliCommandMetadata(
        id="ct_delete_dataset",
        logical_component="container",
        description="Delete a dataset of a selected container: unregister it, and with --purge delete its folder too.",
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that holds the dataset, by storage identifier or filesystem path. "
                    "Optional: when omitted, the container is resolved from the current working directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--purge"],
                "valued": False,
                "description": "Also delete the folder of the dataset from the disk. Without it the disk is left as it is.",
                "type": "bool",
            },
        ],
    )

    CONTAINER_FLAG: ClassVar[str] = "--container"
    DATASET_FLAG: ClassVar[str] = "--delete-dataset"
    PURGE_FLAG: ClassVar[str] = "--purge"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """Match the dataset deletion command at the CLI routing stage."""
        if not args or args[0] != "container":
            return False

        return ContainerDeleteDatasetCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._values(self._request.command_args) is not None

    @staticmethod
    def _values(scoped_args: List[str]) -> Optional[Tuple[str, bool]]:
        """
        The name of the dataset these scoped args delete and whether the folder is purged, or None when they do not
        delete one. ``--delete-dataset`` is required and takes the name; ``--container`` and ``--purge`` are optional,
        in any order.
        """
        remaining: List[str] = list(scoped_args)
        purge: bool = ContainerDeleteDatasetCommand.PURGE_FLAG in remaining
        if purge:
            remaining.remove(ContainerDeleteDatasetCommand.PURGE_FLAG)

        container_at: int = remaining.index(ContainerDeleteDatasetCommand.CONTAINER_FLAG) if ContainerDeleteDatasetCommand.CONTAINER_FLAG in remaining else -1
        if container_at != -1:
            if container_at + 1 >= len(remaining):
                return None
            del remaining[container_at:container_at + 2]

        if ContainerDeleteDatasetCommand.DATASET_FLAG not in remaining:
            return None
        dataset_at: int = remaining.index(ContainerDeleteDatasetCommand.DATASET_FLAG)
        if dataset_at + 1 >= len(remaining) or not remaining[dataset_at + 1].strip():
            return None
        name: str = remaining[dataset_at + 1].strip()
        del remaining[dataset_at:dataset_at + 2]

        return None if remaining else (name, purge)

    def run(self) -> CommandResponse:
        values: Optional[Tuple[str, bool]] = self._values(self._request.command_args)
        if values is None:
            raise CliCommandArgumentException("A dataset name is required after --delete-dataset.")

        name, purge = values
        container_value: object = self._request.context.get_parameter_value("container_path")
        if not isinstance(container_value, str) or not container_value.strip():
            raise CliCommandArgumentException("Required parameter is missing: container_path")

        container_path: Path = Path(container_value).expanduser().resolve()
        dataset_path: Path = RegisteredDatasets.named(container_path, name)
        if dataset_path.parent != container_path:
            raise CliCommandArgumentException(f"The dataset {dataset_path} is not a folder directly in the container {container_path}.")

        RegisteredDatasets.unregister(container_path, dataset_path)
        if purge:
            shutil.rmtree(dataset_path)

        return CommandResponse(
            title="Dataset Purged" if purge else "Dataset Unregistered",
            description=(
                f"Dataset '{name}' was unregistered and its folder was deleted."
                if purge
                else f"Dataset '{name}' was unregistered; its folder was left on the disk."
            ),
            content={"dataset_path": str(dataset_path), "container_path": str(container_path), "purged": purge},
        )
