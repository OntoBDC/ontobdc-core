from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.shared.adapter.parameter import RequiredParameter


class CommentCreateCommand(CliCommandPort):
    """
    Comment on an entity a container keeps.

    The entity is the one whose global id ``--guid`` gives, and it has to be
    one that can be commented on: the facade of its type declares
    ``facade:isCommentable``. The comment goes at the end of the thread of the
    entity, or in reply to a comment of it when ``--reply-to`` says which.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="comment_create",
        logical_component="comment",
        description="Comment on an entity of a container.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "entity_guid",
                "description": "Global id of the entity to comment on.",
                "type": "str",
                "usage": "ontobdc comment --guid <id> --create <text> [--container <id>] [--author <name>] [--reply-to <comment id>]",
            },
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "comment_text",
                "description": "The text of the comment.",
                "type": "str",
            },
            {
                "accepts": ["--author"],
                "valued": True,
                "parameter": "comment_author",
                "description": "Who says it. When omitted, the comment has no author.",
                "type": "str",
            },
            {
                "accepts": ["--reply-to"],
                "valued": True,
                "parameter": "comment_reply_to",
                "description": "Global id of the comment of the thread this one answers.",
                "type": "str",
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
    CREATE_FLAG: ClassVar[str] = "--create"
    AUTHOR_FLAG: ClassVar[str] = "--author"
    REPLY_FLAG: ClassVar[str] = "--reply-to"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    GUID_KEY: ClassVar[str] = "entity_guid"
    TEXT_KEY: ClassVar[str] = "comment_text"
    AUTHOR_KEY: ClassVar[str] = "comment_author"
    REPLY_KEY: ClassVar[str] = "comment_reply_to"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment creation at the CLI routing stage.
        """
        if not args or args[0] != CommentCreateCommand.COMPONENT:
            return False

        return CommentCreateCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        ContainerEntityRepository.provide(context)
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        guid: str = RequiredParameter.of(context, self.GUID_KEY)
        text: str = RequiredParameter.of(context, self.TEXT_KEY).strip()
        if not text:
            raise ValueError("The comment has no text.")

        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        dataset_path: Path
        facade: EntityFacade
        dataset_path, _, facade = ContainerEntityStore(repository, container_path).locate(guid)
        if not facade.commentable:
            raise ValueError(
                f"The entity {guid} cannot be commented on: the facade of its "
                "type does not declare it commentable."
            )

        comment: Dict[str, Any] = CommentThread(dataset_path, guid).add(
            text,
            author=RequiredParameter.optional(context, self.AUTHOR_KEY) or "",
            reply_of=RequiredParameter.optional(context, self.REPLY_KEY),
        )

        return CommandResponse(
            title="Comment Created",
            description=f"Commented on the entity {guid}.",
            content={"entity": guid, **comment},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid and --create, each with a
        value, and optionally --author, --reply-to and --container, each with
        a value, in any order.
        """
        if len(scoped_args) % 2 != 0:
            return False

        pairs: List[Tuple[str, str]] = list(zip(scoped_args[0::2], scoped_args[1::2]))
        flags: List[str] = [flag for flag, _ in pairs]
        allowed: List[str] = [
            CommentCreateCommand.GUID_FLAG,
            CommentCreateCommand.CREATE_FLAG,
            CommentCreateCommand.AUTHOR_FLAG,
            CommentCreateCommand.REPLY_FLAG,
            CommentCreateCommand.CONTAINER_FLAG,
        ]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if CommentCreateCommand.GUID_FLAG not in flags or CommentCreateCommand.CREATE_FLAG not in flags:
            return False

        # The text may start with dashes: only the other values may not look like a flag.
        return all(
            value.strip() and (flag == CommentCreateCommand.CREATE_FLAG or not value.startswith("--"))
            for flag, value in pairs
        )
