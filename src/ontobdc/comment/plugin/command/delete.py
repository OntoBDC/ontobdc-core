from pathlib import Path
from typing import Any, ClassVar, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.shared.adapter.parameter import RequiredParameter


class CommentDeleteCommand(CliCommandPort):
    """
    Remove a comment of a container.

    The comment is the one whose global id ``--delete`` gives, wherever in
    the container its thread is. The comments that reply to it go with it,
    and the ones that reply to those.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="comment_delete",
        logical_component="comment",
        description="Remove a comment of a container, with its replies.",
        arguments=[
            {
                "accepts": ["--delete"],
                "valued": True,
                "parameter": "comment_id",
                "description": "Global id of the comment to remove.",
                "type": "str",
                "usage": "ontobdc comment --delete <comment id> [--container <id>]",
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
    DELETE_FLAG: ClassVar[str] = "--delete"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    COMMENT_KEY: ClassVar[str] = "comment_id"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment removal at the CLI routing stage.
        """
        if not args or args[0] != CommentDeleteCommand.COMPONENT:
            return False

        return CommentDeleteCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        comment_id: str = RequiredParameter.of(context, self.COMMENT_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        thread: Optional[CommentThread] = CommentThread.holding(container_path, comment_id)
        if thread is None:
            raise LookupError(f"No thread the container keeps has the comment {comment_id}.")

        removed: List[str] = thread.delete(comment_id)
        return CommandResponse(
            title="Comment Deleted",
            description=f"Removed {len(removed)} comments, from the comment {comment_id}.",
            content={"global_id": comment_id, "removed": removed},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --delete with a value, and
        optionally --container with a value, in any order.
        """
        if len(scoped_args) % 2 != 0:
            return False

        pairs: List[Tuple[str, str]] = list(zip(scoped_args[0::2], scoped_args[1::2]))
        flags: List[str] = [flag for flag, _ in pairs]
        if sorted(flags) not in (
            [CommentDeleteCommand.DELETE_FLAG],
            sorted([CommentDeleteCommand.DELETE_FLAG, CommentDeleteCommand.CONTAINER_FLAG]),
        ):
            return False

        return all(value.strip() and not value.startswith("--") for _, value in pairs)
