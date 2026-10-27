from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.shared.adapter.parameter import RequiredParameter


class ContainerEntityInspectCommand(CliCommandPort):
    """
    Command for inspecting one entity a container keeps, again.

    The entity is the one whose global id ``--entity`` gives. The answer has
    the shape of the listing of ``--entity``, with the one dataset that keeps
    the entity and only that entity in it, so whoever shows the entity can put it
    in place of the one it has without reading the others.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_inspect",
        logical_component="container",
        description="Inspect one entity of a container, as it is kept now.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_id",
                "description": "Global id of the entity to inspect.",
                "type": "str",
                "usage": "ontobdc container --entity <id> --inspect [--container <id-or-path>]",
            },
            {
                "accepts": ["--inspect"],
                "description": "Inspect the entity.",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that keeps the entity, by storage "
                    "identifier or filesystem path. When omitted, it is "
                    "resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    INSPECT_FLAG: ClassVar[str] = "--inspect"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_id"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity inspection at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityInspectCommand.COMPONENT:
            return False

        return ContainerEntityInspectCommand._matches(args[1:])

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
        global_id: str = RequiredParameter.of(context, self.ENTITY_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        dataset: Dict[str, Any]
        for dataset in ContainerEntities.of(container_path):
            entities: List[Dict[str, Any]] = [
                entity
                for entity in dataset["entities"]
                if entity.get("global_id") == global_id
            ]
            if entities:
                return CommandResponse(
                    title="Container Entity",
                    description=(
                        f"Inspect the entity {global_id} of the container "
                        f"«{container_path.name}»."
                    ),
                    content={"datasets": [{**dataset, "entities": entities}]},
                )

        raise LookupError(
            f"The container «{container_path.name}» keeps no entity {global_id}."
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity with a value,
        --inspect with none, and optionally --container with a value, in
        any order.
        """
        if ContainerEntityInspectCommand.INSPECT_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument
            for argument in scoped_args
            if argument != ContainerEntityInspectCommand.INSPECT_FLAG
        ]
        if len(remaining) % 2 != 0 or len(remaining) != len(scoped_args) - 1:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[List[str]] = [
            [ContainerEntityInspectCommand.ENTITY_FLAG],
            sorted([ContainerEntityInspectCommand.ENTITY_FLAG, ContainerEntityInspectCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
