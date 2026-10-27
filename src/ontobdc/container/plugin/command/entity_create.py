from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.context.plugin.capability.transformation.entity_uri_resolved import (
    EntityUriResolvedCapability,
)
from ontobdc.container.adapter.entity_creation import EntityCreation
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.command.entity_update import ContainerEntityUpdateCommand
from ontobdc.container.plugin.machine.entity_write.machine import (
    EntityWriteRequest,
    EntityWriteStateTransitionHandler,
)


class ContainerEntityCreateCommand(CliCommandPort):
    """
    Command for creating an instance of an entity in a container.

    The entity is the type ``--entity`` gives, by its IRI or a name OntoBDC
    knows, and the values come from ``--create`` the way ``--update`` takes
    them: a path to a ``.json`` or ``.csv`` file, a JSON object written in
    place, or ``key=value`` assignments separated by commas. The facade of the
    entity decides everything else: it must allow creating instances, a field
    it gives a default (a generated identifier, the moment of creation) gets
    it when the value was not given, and the fields it requires must end up
    with a value. The row is written, by the process of writing entities,
    through the entity repository the context carries; OntoBDC has no default
    one, so without it this fails, before anything is read.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_create",
        logical_component="container",
        description="Create an instance of an entity in a container.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_type",
                "description": "The entity to create an instance of: its IRI, or a name OntoBDC knows.",
                "type": "str",
                "usage": "ontobdc container --entity <type> --create <source> [--container <id-or-path>]",
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "entity_create_source",
                "description": (
                    "The values of the new instance: a path to a .json or .csv "
                    "file, a JSON object, or key=value assignments separated by commas."
                ),
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container the instance is created in, by storage "
                    "identifier or filesystem path. When omitted, it is "
                    "resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    CREATE_FLAG: ClassVar[str] = "--create"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_type"
    SOURCE_KEY: ClassVar[str] = "entity_create_source"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity creation at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityCreateCommand.COMPONENT:
            return False

        return ContainerEntityCreateCommand._matches(args[1:])

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

        entity_iri: str = str(
            EntityUriResolvedCapability.resolve(RequiredParameter.of(context, self.ENTITY_KEY))
        )
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        given: Dict[str, Any] = ContainerEntityUpdateCommand.parse(
            RequiredParameter.of(context, self.SOURCE_KEY)
        )

        facade: EntityFacade = EntityFacadeLocator.of(entity_iri)
        record: Dict[str, Any] = EntityCreation.record(facade, given)
        global_id: str = str(record.get(EntityCreation.IDENTIFIER_FIELD, "")).strip()
        if not global_id:
            raise ValueError(
                f"The facade of <{entity_iri}> gives no {EntityCreation.IDENTIFIER_FIELD}: "
                "the instance would have no identity."
            )
        if ContainerEntityStore(repository, container_path).exists(global_id):
            raise ValueError(f"An entity with the global id {global_id} already exists.")

        keys: List[str] = [
            EntityWriteRequest.CONTAINER_PATH_KEY,
            EntityWriteRequest.ENTITY_IRI_KEY,
            EntityWriteRequest.RECORDS_KEY,
            EntityWriteRequest.SOURCE_DOCUMENTS_KEY,
            EntityWriteRequest.DATASET_PATH_KEY,
        ]
        context.set_parameter_value(EntityWriteRequest.CONTAINER_PATH_KEY, str(container_path))
        context.set_parameter_value(EntityWriteRequest.ENTITY_IRI_KEY, entity_iri)
        context.set_parameter_value(EntityWriteRequest.RECORDS_KEY, [record])
        context.set_parameter_value(EntityWriteRequest.SOURCE_DOCUMENTS_KEY, [])
        try:
            written: CommandResponse = EntityWriteStateTransitionHandler(context).execute()
        finally:
            key: str
            for key in keys:
                context.delete_parameter(key)

        return CommandResponse(
            title="Entity Created",
            description=f"Created the entity {global_id}.",
            content={"global_id": global_id, "record": record, "dataset_path": written.content.get("dataset_path")},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity and --create, and
        optionally --container, each with a value, in any order.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        required: List[str] = [
            ContainerEntityCreateCommand.ENTITY_FLAG,
            ContainerEntityCreateCommand.CREATE_FLAG,
        ]
        allowed: List[str] = required + [ContainerEntityCreateCommand.CONTAINER_FLAG]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in required):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
