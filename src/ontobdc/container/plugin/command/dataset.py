from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple

from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.container.adapter.dataset import DatasetTitleRepository
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.container.plugin.check.is_dataset_metadata_ready.hotfix import (
    main as create_dataset_metadata,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.hotfix import (
    main as index_dataset_in_container,
)


class ContainerCreateDatasetCommand(CliCommandPort):
    """
    Command for creating a dataset inside a selected container.

    The container selector is declared here and resolved by the parameter
    stage before ``check`` runs, so this command never reaches for a selector
    strategy itself. Creation writes the dataset metadata, replaces the
    generated name with the title the user gave, and indexes the dataset in
    its container.
    """

    METADATA = CliCommandMetadata(
        id="ct_create_dataset",
        logical_component="container",
        description="Create a new dataset inside a selected container.",
        arguments=[
            {
                "accepts": [
                    "--container",
                ],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that will hold the new "
                    "dataset, by storage identifier or filesystem path. "
                    "The dataset is created as a subfolder of the "
                    "container with its own metadata, title and index "
                    "entry; its title is given alongside "
                    "--create-dataset."
                ),
            },
        ],
    )

    CONTAINER_FLAG: ClassVar[str] = "--container"
    DATASET_FLAG: ClassVar[str] = "--create-dataset"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dataset creation command at the CLI routing stage.
        """
        if not args or args[0] != "container":
            return False

        return ContainerCreateDatasetCommand._values(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        values: Optional[Tuple[str, str]] = self._values(
            self._request.command_args
        )
        if values is None:
            return False

        dataset_title: str = values[1]

        dataset_slug: str = TitleSlug.of(dataset_title)
        if not dataset_slug:
            raise CliCommandArgumentException(
                f"Invalid dataset title: {dataset_title}. It must contain at "
                f"least one letter or digit."
            )

        self._request.context.delete_parameter("dataset_path")
        self._request.context.set_parameter_value("dataset_title", dataset_title)
        self._request.context.set_parameter_value("dataset_slug", dataset_slug)

        return True

    @staticmethod
    def _values(scoped_args: List[str]) -> Optional[Tuple[str, str]]:
        """
        Return the (container, dataset title) pair these scoped args name,
        with --container and --create-dataset in either order, or None when
        they do not name one.

        Both flags are required here -- there is no current-directory
        fallback for which container to create the dataset in -- but which
        one a user writes first is not part of the command's meaning.
        """
        remaining: List[str] = list(scoped_args)
        container_value: Optional[str] = ContainerCreateDatasetCommand._extract(
            remaining, ContainerCreateDatasetCommand.CONTAINER_FLAG
        )
        dataset_value: Optional[str] = ContainerCreateDatasetCommand._extract(
            remaining, ContainerCreateDatasetCommand.DATASET_FLAG
        )
        if container_value is None or dataset_value is None or remaining:
            return None

        return container_value, dataset_value

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        """
        Remove and return the value following flag in remaining, or None
        when the flag is absent or has no value after it.
        """
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip():
            return None

        del remaining[index:index + 2]
        return value.strip()

    def run(self) -> CommandResponse:
        """
        Create the dataset inside the selected container.
        """
        dataset_title: str = self._required_parameter("dataset_title")
        dataset_slug: str = self._required_parameter("dataset_slug")
        container_path: Path = Path(
            self._required_parameter("container_path")
        ).expanduser().resolve()
        root_path: str = self._request.context.root_path
        dataset_path: Path = container_path / dataset_slug

        if dataset_path.exists():
            raise CliCommandArgumentException(
                f"The container already holds a dataset at {dataset_path}."
            )

        if create_dataset_metadata(
            dataset_path=str(dataset_path),
            root_path=root_path,
        ) != 0:
            raise RuntimeError(
                f"Failed to write the metadata of the dataset at {dataset_path}."
            )

        DatasetTitleRepository(dataset_path).write_title(dataset_title)

        if index_dataset_in_container(
            dataset_path=str(dataset_path),
            root_path=root_path,
        ) != 0:
            raise RuntimeError(
                f"Failed to index the dataset at {dataset_path} in its container."
            )

        self._request.context.set_parameter_value("dataset_path", str(dataset_path))

        return CommandResponse(
            title="Dataset Created",
            description=f"Dataset '{dataset_title}' created successfully.",
            content={
                "dataset_title": dataset_title,
                "dataset_slug": dataset_slug,
                "dataset_path": str(dataset_path),
                "container_path": str(container_path),
            },
        )

    def _required_parameter(self, name: str) -> str:
        """
        Return the value the context carries under the given name.
        """
        value: Any = self._request.context.get_parameter_value(name)
        if not isinstance(value, str) or not value.strip():
            raise CliCommandArgumentException(
                f"Required parameter is missing: {name}"
            )

        return value.strip()
