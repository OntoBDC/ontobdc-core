import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.command.update import (
    ContainerUpdateSource,
    ContainerUpdateSourceKind,
    ContainerUpdateSourceParser,
)
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest


class ContainerEntityUpdateCommand(CliCommandPort):
    """
    Command for changing the fields of an entity a container keeps.

    The entity is the one whose global id ``--entity`` gives, and the new
    values come from ``--update``: a path to a ``.json`` or ``.csv`` file, a
    JSON object written in place, or ``key=value`` assignments separated by
    commas. The keys are the identifiers of the fields. The row is written
    through the entity repository the context carries; OntoBDC has no
    default one, so without it this fails, before anything is read.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_update",
        logical_component="container",
        description="Change the fields of an entity of a container.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_id",
                "description": "Global id of the entity to change.",
                "type": "str",
                "usage": "ontobdc container --entity <id> --update <source> [--container <id-or-path>]",
            },
            {
                "accepts": ["--update"],
                "valued": True,
                "parameter": "entity_update_source",
                "description": (
                    "The values to write: a path to a .json or .csv file, a "
                    "JSON object, or key=value assignments separated by commas."
                ),
                "type": "str",
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
    UPDATE_FLAG: ClassVar[str] = "--update"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_id"
    SOURCE_KEY: ClassVar[str] = "entity_update_source"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity update at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityUpdateCommand.COMPONENT:
            return False

        return ContainerEntityUpdateCommand._matches(args[1:])

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
        # Before anything is read of an entity that could not be kept.
        ContainerEntityRepository.provide(context)
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        global_id: str = RequiredParameter.of(context, self.ENTITY_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        changes: Dict[str, Any] = self.parse(RequiredParameter.of(context, self.SOURCE_KEY))

        changed: List[str] = ContainerEntityStore(repository, container_path).update(
            global_id, changes
        )

        return CommandResponse(
            title="Entity Updated",
            description=f"Changed {', '.join(changed) or 'nothing'} of the entity {global_id}.",
            content={"global_id": global_id, "changed": changed},
        )

    @staticmethod
    def parse(source: str) -> Dict[str, Any]:
        """
        The values the source gives, by field identifier.
        """
        value: str = source.strip()
        if value.startswith("{"):
            try:
                parsed: Any = json.loads(value)
            except ValueError as error:
                raise CliCommandArgumentException(f"Invalid JSON entity update: {error}") from error
            if not isinstance(parsed, dict):
                raise CliCommandArgumentException("An entity update in JSON must be an object.")

            return parsed

        kind: Optional[ContainerUpdateSourceKind] = ContainerUpdateSource.classify(value)
        if kind is None:
            raise CliCommandArgumentException(f"Invalid entity update source: {value}")

        return ContainerUpdateSourceParser.parse(value, kind)

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity and --update, and
        optionally --container, each with a value, in any order.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        required: List[str] = [
            ContainerEntityUpdateCommand.ENTITY_FLAG,
            ContainerEntityUpdateCommand.UPDATE_FLAG,
        ]
        allowed: List[str] = required + [ContainerEntityUpdateCommand.CONTAINER_FLAG]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in required):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
