from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.container_triple import ContainerTriple
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerTripleFindCommand(CliCommandPort):
    """
    Command for reading what the ``container.ttl`` of a container says of a subject.

    The value of ``--triple`` is the subject alone, and then every predicate of the subject comes with its objects, or the
    subject and the predicate, separated by ``;``, and then only the objects of that predicate. See
    :class:`ContainerTriple` for how the terms are written.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_triple_find",
        logical_component="container",
        description="List what the container.ttl of a container says of a subject.",
        arguments=[
            {
                "accepts": ["--triple"],
                "valued": True,
                "parameter": "triple_query",
                "description": (
                    "The subject, to list every predicate of it with its objects, or subject;predicate, to list the "
                    "objects of that predicate. Each term is a full IRI between < and > or a name with a prefix the "
                    "container.ttl declares."
                ),
                "type": "str",
                "usage": "ontobdc container --triple '<subject>[;<predicate>]' [--container <id-or-path>]",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container, by storage identifier or filesystem path. When omitted, it is resolved "
                    "from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    TRIPLE_FLAG: ClassVar[str] = "--triple"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    TRIPLE_KEY: ClassVar[str] = "triple_query"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContainerTripleFindCommand.COMPONENT:
            return False

        return ContainerTripleFindCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        query: str = str(RequiredParameter.of(context, self.TRIPLE_KEY))
        container_path: Path = Path(RequiredParameter.of(context, self.CONTAINER_KEY)).expanduser().resolve()

        subject: str
        predicates: Dict[str, List[str]]
        container_file: Path = StorageBootstrap.get_container_storage_file_path(container_path)
        subject, predicates = ContainerTriple.find(container_file, query)
        if not predicates:
            raise LookupError(f"{container_file} says nothing of {query}.")

        return CommandResponse(
            title="Container Triple",
            description=f"What the container.ttl says of {subject}.",
            content={"subject": subject, "predicates": predicates, "container": str(container_path)},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --triple with a value and optionally --container with a value, in any
        order.
        """
        if ContainerTripleFindCommand.TRIPLE_FLAG not in scoped_args:
            return False

        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[List[str]] = [
            [ContainerTripleFindCommand.TRIPLE_FLAG],
            sorted([ContainerTripleFindCommand.TRIPLE_FLAG, ContainerTripleFindCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
