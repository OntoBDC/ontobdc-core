from typing import ClassVar, List, Optional

from ontobdc.context.plugin.machine.entity_inspection.machine import (
    EntityInspectionStateTransitionHandler,
)

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse


class ContextEntityInspectCommand(CliCommandPort):
    """Inspect the facade brasidatacenter publishes for an entity IRI, or list the entities."""

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="context_entity_inspect",
        logical_component="context",
        description="Inspect the facade published for an entity, or list every entity.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "optional": True,
                "parameter": "entity_id",
                "description": (
                    "IRI of the entity to inspect. When omitted, list every "
                    "entity brasidatacenter publishes."
                ),
                "type": "str",
            },
            {
                "accepts": ["--inspect"],
                "description": "Request the entity's facade (or the list of entities) from brasidatacenter.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "context"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    INSPECT_FLAG: ClassVar[str] = "--inspect"
    ENTITY_CONTEXT_KEY: ClassVar[str] = "entity_id"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContextEntityInspectCommand.COMPONENT:
            return False
        return ContextEntityInspectCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        entity_id: Optional[str] = self._extract_entity(
            self._request.command_args
        )
        if entity_id is None:
            return False
        # Without a value, the generic binding took the next flag as the
        # value of --entity: the empty string replaces it, and means "list".
        self._request.context.set_parameter_value(
            self.ENTITY_CONTEXT_KEY, entity_id
        )
        return True

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        return (
            ContextEntityInspectCommand._extract_entity(scoped_args)
            is not None
        )

    @staticmethod
    def _extract_entity(scoped_args: List[str]) -> Optional[str]:
        """
        The entity IRI of ``--entity <iri> --inspect``, the empty string for
        ``--entity --inspect`` (list every entity), or None when the
        arguments are neither.
        """
        if ContextEntityInspectCommand.INSPECT_FLAG not in scoped_args:
            return None

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContextEntityInspectCommand.INSPECT_FLAG)
        if remaining == [ContextEntityInspectCommand.ENTITY_FLAG]:
            return ""

        if (
            len(remaining) == 2
            and remaining[0] == ContextEntityInspectCommand.ENTITY_FLAG
            and remaining[1].strip()
            and not remaining[1].startswith("--")
        ):
            return remaining[1].strip()

        return None

    def run(self) -> CommandResponse:
        return EntityInspectionStateTransitionHandler(
            context=self._request.context
        ).execute()
