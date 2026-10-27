from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.shared.adapter.parameter import RequiredParameter


class CommentUpdateCommand(CliCommandPort):
    """
    Change a comment of a container: what it says, who says it, or both.

    The comment is the one whose global id ``--update`` gives, wherever in the container its thread
    is. What is not given stays as it was; the comment keeps its place in the thread.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="comment_update",
        logical_component="comment",
        description="Change the text or the author of a comment of a container.",
        arguments=[
            {
                "accepts": ["--update"],
                "valued": True,
                "parameter": "comment_id",
                "description": "Global id of the comment to change.",
                "type": "str",
                "usage": "ontobdc comment --update <comment id> [--text <text>] [--author <name>] [--container <id>]",
            },
            {
                "accepts": ["--text"],
                "valued": True,
                "parameter": "comment_text",
                "description": "What the comment says from now on.",
                "type": "str",
            },
            {
                "accepts": ["--author"],
                "valued": True,
                "parameter": "comment_author",
                "description": "Who says it from now on.",
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that keeps the comment, by storage "
                    "identifier. When omitted, the container is resolved from "
                    "the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "comment"
    UPDATE_FLAG: ClassVar[str] = "--update"
    TEXT_FLAG: ClassVar[str] = "--text"
    AUTHOR_FLAG: ClassVar[str] = "--author"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    COMMENT_KEY: ClassVar[str] = "comment_id"
    TEXT_KEY: ClassVar[str] = "comment_text"
    AUTHOR_KEY: ClassVar[str] = "comment_author"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment change at the CLI routing stage.
        """
        if not args or args[0] != CommentUpdateCommand.COMPONENT:
            return False

        return CommentUpdateCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        comment_id: str = RequiredParameter.of(context, self.COMMENT_KEY)
        text: Optional[str] = RequiredParameter.optional(context, self.TEXT_KEY)
        author: Optional[str] = RequiredParameter.optional(context, self.AUTHOR_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        thread: Optional[CommentThread] = CommentThread.holding(container_path, comment_id)
        if thread is None:
            raise LookupError(f"No thread the container keeps has the comment {comment_id}.")

        comment: Dict[str, Any] = thread.update(comment_id, text, author)
        return CommandResponse(
            title="Comment Updated",
            description=f"Changed the comment {comment_id}.",
            content=comment,
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --update with a value, with --text and/or --author, each
        with a value, and optionally --container with a value, in any order.
        """
        if len(scoped_args) % 2 != 0:
            return False

        pairs: List[Tuple[str, str]] = list(zip(scoped_args[0::2], scoped_args[1::2]))
        flags: List[str] = [flag for flag, _ in pairs]
        allowed: List[str] = [
            CommentUpdateCommand.UPDATE_FLAG,
            CommentUpdateCommand.TEXT_FLAG,
            CommentUpdateCommand.AUTHOR_FLAG,
            CommentUpdateCommand.CONTAINER_FLAG,
        ]
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if CommentUpdateCommand.UPDATE_FLAG not in flags:
            return False
        if CommentUpdateCommand.TEXT_FLAG not in flags and CommentUpdateCommand.AUTHOR_FLAG not in flags:
            return False

        return all(value.strip() and not value.startswith("--") for _, value in pairs)
