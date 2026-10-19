from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.context.plugin.capability.transformation.entity_uri_resolved import (
    EntityUriResolvedCapability,
)
from ontobdc.container.adapter.entity_tree import ContainerEntityTree


class ContainerEntityTreeCommand(CliCommandPort):
    """
    Command for listing the instances of one entity type a registered
    container holds, as a tree.

    The entity is the type ``--entity`` gives, by its IRI or a name OntoBDC
    knows. Its instances are the first level; what is below each one comes from
    the facades (``facade:hasTreeViewChild``) and from the relations the
    datasets, all of them together, say between the entities.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity_tree",
        logical_component="container",
        description="List the instances of an entity type in a registered container as a tree, as its facade declares.",
        depends_on=None,
        arguments=[
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container whose entities are listed, by "
                    "storage identifier or filesystem path. When omitted, "
                    "resolve the container from the current working "
                    "directory."
                ),
                "type": "str",
            },
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_type",
                "description": "The entity type whose instances are the roots of the tree: its IRI, or a name OntoBDC knows.",
                "type": "str",
            },
            {
                "accepts": ["--tree"],
                "description": (
                    "List the instances of the entity type, each with the "
                    "entities below it that the facade of its type declares "
                    "(facade:hasTreeViewChild), found in what the datasets say."
                ),
                "usage": "ontobdc container --entity <type> --tree [--container <id-or-path>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    TREE_FLAG: ClassVar[str] = "--tree"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    ENTITY_KEY: ClassVar[str] = "entity_type"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the entity listing by type at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityTreeCommand.COMPONENT:
            return False

        return ContainerEntityTreeCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        if not self._matches(self._request.command_args):
            return False

        container_path: Any = self._request.context.get_parameter_value(
            self.CONTAINER_KEY
        )

        return isinstance(container_path, str) and bool(container_path.strip())

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --entity with a value and
        --tree, and optionally --container with a value, in any order.
        """
        remaining: List[str] = list(scoped_args)
        if remaining.count(ContainerEntityTreeCommand.TREE_FLAG) != 1:
            return False

        remaining.remove(ContainerEntityTreeCommand.TREE_FLAG)
        if len(remaining) % 2 != 0:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[str] = [
            ContainerEntityTreeCommand.ENTITY_FLAG,
            ContainerEntityTreeCommand.CONTAINER_FLAG,
        ]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if ContainerEntityTreeCommand.ENTITY_FLAG not in flags:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)

    def run(self) -> CommandResponse:
        """
        List the instances of the entity type with the entities below them.
        """
        context: Any = self._request.context
        entity_iri: str = str(
            EntityUriResolvedCapability.resolve(RequiredParameter.of(context, self.ENTITY_KEY))
        )
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        nodes: List[Dict[str, Any]] = ContainerEntityTree.of(container_path, entity_iri)

        return CommandResponse(
            title="Container Entity Tree",
            description=(
                f"{len(nodes)} entities of <{entity_iri}> in the container "
                f"«{container_path.name}», with the entities below them."
            ),
            content={"entity_iri": entity_iri, "nodes": nodes},
        )
