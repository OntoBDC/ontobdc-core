import re
from typing import ClassVar, List, Pattern

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import (
    CommandResponse,
    ExceptionCommandResponse,
)
from ontobdc.cli.domain.exception.command import CliCommandArgumentException


class TagListParser:
    """
    Reads the tag list a user typed into the tags it names.

    A user separates tags with whatever their keyboard offers first, so a
    space, a comma, a semicolon, a pipe and a slash all separate; a tag
    itself carries none of them. The order the user typed is the order the
    tags keep, and a tag repeated in the list is kept once.
    """

    SEPARATORS: ClassVar[str] = " ,;|/"
    _SEPARATOR: ClassVar[Pattern[str]] = re.compile(r"[ ,;|/]+")

    @classmethod
    def parse(cls, tag_list: str) -> List[str]:
        """
        Return the tags the given list names, in the order they were typed.
        """
        tags: List[str] = []
        tag: str
        for tag in cls._SEPARATOR.split(tag_list.strip()):
            if not tag or tag in tags:
                continue

            tags.append(tag)

        return tags


class RunTagCommand(CliCommandPort):
    """
    Command for running every capability that carries the given tags.

    Routing, argument validation and the tag list parsing are in place. The
    capability selection that the tags drive has not been restored yet, so
    ``run`` reports that instead of running anything.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="tag",
        logical_component="run",
        description="Execute every capability carrying the given tags.",
        depends_on=None,
        arguments=[
            {
                "accepts": [
                    "--tag",
                ],
                "valued": True,
                "parameter": "tag_list",
                "description": (
                    "Filter which capabilities run by tags declared in "
                    "their METADATA. Accept one or more tags separated by "
                    "whitespace, comma, semicolon, pipe or slash; only "
                    "capabilities that carry at least one matching tag "
                    "execute."
                ),
            },
        ],
    )

    TAG_FLAG: ClassVar[str] = "--tag"

    # Kept short on purpose: the widget adapter renders this value inside a
    # fenced block, which the terminal surface prints verbatim, without
    # wrapping it to the frame width.
    _PENDING_ERROR: ClassVar[str] = "Tag capability selection not restored."
    _PENDING_REASON: ClassVar[str] = (
        "Running capabilities by tag is not available in this build: the "
        "capability selection the tags drive has not been restored yet."
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the tag run command at the CLI routing stage.
        """
        return (
            len(args) == 3
            and args[0] == "run"
            and args[1] == RunTagCommand.TAG_FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        command_args: List[str] = self._request.command_args
        if not (len(command_args) == 2 and command_args[0] == self.TAG_FLAG):
            return False

        tag_list: str = command_args[1].strip()
        if not tag_list:
            return False

        tags: List[str] = TagListParser.parse(tag_list)
        if not tags:
            raise CliCommandArgumentException(
                f"Invalid tag list: {tag_list}. It must name at least one "
                f"tag, separated by any of: {TagListParser.SEPARATORS}."
            )

        self._request.context.set_parameter_value("tags", tags)

        return True

    def run(self) -> CommandResponse:
        """
        Report that running capabilities by tag is not available yet.
        """
        return ExceptionCommandResponse(
            title="Tag Run Not Available",
            description=self._PENDING_REASON,
            content={
                "error": self._PENDING_ERROR,
                "tags": self._request.context.get_parameter_value("tags"),
            },
        )
