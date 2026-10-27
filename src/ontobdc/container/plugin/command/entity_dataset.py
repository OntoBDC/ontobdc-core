from pathlib import Path
from typing import Any, ClassVar, List, Optional

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.plugin.capability.transformation.dataset_found import (
    DatasetFoundCapability,
)
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.context.plugin.capability.transformation.entity_uri_resolved import (
    EntityUriResolvedCapability,
)
from ontobdc.shared.adapter.parameter import RequiredParameter


class ContainerEntityDatasetCommand(CliCommandPort):
    """
    Command for making sure a container has a dataset for an entity type.

    The entity is the type ``--entity`` gives, by its IRI or a name OntoBDC
    knows. When the container already has a dataset that holds it, nothing
    changes; when it has none, one is created, named after the facade of the
    entity, and left empty: it is what the first instance written would have
    created anyway.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_dataset",
        logical_component="container",
        description="Make sure a container has a dataset for an entity type.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_type",
                "description": "The entity the dataset must hold: its IRI, or a name OntoBDC knows.",
                "type": "str",
                "usage": "ontobdc container --entity <type> --dataset [--container <id-or-path>]",
            },
            {
                "accepts": ["--dataset"],
                "description": "Create the dataset of the entity when the container has none.",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container, by storage identifier or filesystem "
                    "path. When omitted, it is resolved from the current "
                    "working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    DATASET_FLAG: ClassVar[str] = "--dataset"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_type"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dataset of an entity at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityDatasetCommand.COMPONENT:
            return False

        return ContainerEntityDatasetCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        entity_iri: str = str(
            EntityUriResolvedCapability.resolve(RequiredParameter.of(context, self.ENTITY_KEY))
        )
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        existing: Optional[Path] = EntityDatasets.first(container_path, entity_iri)
        created: bool = existing is None
        dataset_path: Optional[Path] = existing
        if created:
            keys: List[str] = [
                EntityWriteRequest.CONTAINER_PATH_KEY,
                EntityWriteRequest.ENTITY_IRI_KEY,
                EntityWriteRequest.DATASET_PATH_KEY,
                "dataset_title",
            ]
            context.set_parameter_value(EntityWriteRequest.CONTAINER_PATH_KEY, str(container_path))
            context.set_parameter_value(EntityWriteRequest.ENTITY_IRI_KEY, entity_iri)
            try:
                made: Any = DatasetFoundCapability().execute(context)
                dataset_path = Path(made["dataset_path"])
            finally:
                key: str
                for key in keys:
                    context.delete_parameter(key)

        return CommandResponse(
            title="Entity Dataset",
            description=(
                f"Created the dataset of <{entity_iri}>."
                if created
                else f"The container already has the dataset of <{entity_iri}>."
            ),
            content={
                "entity_type": entity_iri,
                "dataset_path": str(dataset_path),
                "created": created,
            },
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity with a value,
        --dataset with none, and optionally --container with a value, in
        any order.
        """
        if ContainerEntityDatasetCommand.DATASET_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument
            for argument in scoped_args
            if argument != ContainerEntityDatasetCommand.DATASET_FLAG
        ]
        if len(remaining) % 2 != 0 or len(remaining) != len(scoped_args) - 1:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[List[str]] = [
            [ContainerEntityDatasetCommand.ENTITY_FLAG],
            sorted([ContainerEntityDatasetCommand.ENTITY_FLAG, ContainerEntityDatasetCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
