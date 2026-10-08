from pathlib import Path
from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest


class ContainerEntityDeleteCommand(CliCommandPort):
    """
    Command for removing an entity a container keeps.

    The entity is the one whose global id ``--entity`` gives. Its row is
    removed through the entity repository the context carries; OntoBDC has
    no default one, so without it this fails, before anything is read. The
    documents the entity referred to are left alone.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_delete",
        logical_component="container",
        description="Remove an entity of a container.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_id",
                "description": "Global id of the entity to remove.",
                "type": "str",
                "usage": "ontobdc container --entity <id> --delete [--container <id-or-path>]",
            },
            {
                "accepts": ["--delete"],
                "description": "Remove the entity.",
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
    DELETE_FLAG: ClassVar[str] = "--delete"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_id"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity delete at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityDeleteCommand.COMPONENT:
            return False

        return ContainerEntityDeleteCommand._matches(args[1:])

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
        # Before anything is read of an entity that could not be removed.
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        global_id: str = RequiredParameter.of(context, self.ENTITY_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        ContainerEntityStore(repository, container_path).delete(global_id)

        return CommandResponse(
            title="Entity Deleted",
            description=f"Removed the entity {global_id}.",
            content={"global_id": global_id},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity with a value,
        --delete with none, and optionally --container with a value, in
        any order.
        """
        if ContainerEntityDeleteCommand.DELETE_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument
            for argument in scoped_args
            if argument != ContainerEntityDeleteCommand.DELETE_FLAG
        ]
        if len(remaining) % 2 != 0 or len(remaining) != len(scoped_args) - 1:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[List[str]] = [
            [ContainerEntityDeleteCommand.ENTITY_FLAG],
            sorted([ContainerEntityDeleteCommand.ENTITY_FLAG, ContainerEntityDeleteCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
