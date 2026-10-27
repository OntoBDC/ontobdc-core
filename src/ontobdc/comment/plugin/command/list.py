from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.shared.adapter.parameter import RequiredParameter


class CommentListCommand(CliCommandPort):
    """
    List the comments of the thread of an entity a container keeps.

    The entity is the one whose global id ``--guid`` gives. The comments are
    the ones of its thread, the oldest first, each with the comment it
    answers, if it answers one. An entity that nobody commented on has an
    empty thread.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="comment_list",
        logical_component="comment",
        description="List the comments of an entity of a container.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "entity_guid",
                "description": "Global id of the entity whose comments are listed.",
                "type": "str",
                "usage": "ontobdc comment --guid <id> --list [--container <id>]",
            },
            {
                "accepts": ["--list"],
                "description": "List the comments of the entity.",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that keeps the entity, by storage "
                    "identifier. When omitted, the container is resolved from "
                    "the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "comment"
    GUID_FLAG: ClassVar[str] = "--guid"
    LIST_FLAG: ClassVar[str] = "--list"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    GUID_KEY: ClassVar[str] = "entity_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment listing at the CLI routing stage.
        """
        if not args or args[0] != CommentListCommand.COMPONENT:
            return False

        return CommentListCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        ContainerEntityRepository.provide(context)
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        guid: str = RequiredParameter.of(context, self.GUID_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        dataset_path: Path
        dataset_path, _, _ = ContainerEntityStore(repository, container_path).locate(guid)
        comments: List[Dict[str, Any]] = CommentThread(dataset_path, guid).comments()

        return CommandResponse(
            title="Comments",
            description=f"{len(comments)} comments on the entity {guid}.",
            content={"entity": guid, "comments": comments},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid with a value, --list with
        none, and optionally --container with a value, in any order.
        """
        if CommentListCommand.LIST_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument for argument in scoped_args if argument != CommentListCommand.LIST_FLAG
        ]
        if len(remaining) % 2 != 0 or len(remaining) != len(scoped_args) - 1:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[List[str]] = [
            [CommentListCommand.GUID_FLAG],
            sorted([CommentListCommand.GUID_FLAG, CommentListCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
