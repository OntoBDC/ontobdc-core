from pathlib import Path
from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.container_triple import ContainerTriple
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerTripleCommand(CliCommandPort):
    """
    Command for writing one triple of an ontology in the ``container.ttl`` of a container.

    The triple is the value of ``--add-triple``: subject, predicate and object, separated by ``;``. See
    :class:`ContainerTriple` for how the terms are written and for what happens with their namespaces.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_triple",
        logical_component="container",
        description="Write a triple of an ontology in the container.ttl of a container.",
        arguments=[
            {
                "accepts": ["--add-triple"],
                "valued": True,
                "parameter": "triple",
                "description": (
                    "The triple, as subject;predicate;object. Each term is a full IRI between < and >, a name with a "
                    "prefix the container.ttl declares or, for the object, a literal."
                ),
                "type": "str",
                "usage": "ontobdc container --add-triple '<subject>;<predicate>;<object>' [--container <id-or-path>]",
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
    TRIPLE_FLAG: ClassVar[str] = "--add-triple"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    TRIPLE_KEY: ClassVar[str] = "triple"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContainerTripleCommand.COMPONENT:
            return False

        return ContainerTripleCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        triple: str = str(RequiredParameter.of(context, self.TRIPLE_KEY))
        container_path: Path = Path(RequiredParameter.of(context, self.CONTAINER_KEY)).expanduser().resolve()

        written: bool = ContainerTriple.write(StorageBootstrap.get_container_storage_file_path(container_path), triple)

        return CommandResponse(
            title="Container Triple",
            description=(
                "Wrote the triple in the container.ttl."
                if written
                else "The container.ttl already had the triple."
            ),
            content={"triple": triple, "container": str(container_path), "written": written},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --add-triple with a value and optionally --container with a value, in any
        order.
        """
        if ContainerTripleCommand.TRIPLE_FLAG not in scoped_args:
            return False

        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[List[str]] = [
            [ContainerTripleCommand.TRIPLE_FLAG],
            sorted([ContainerTripleCommand.TRIPLE_FLAG, ContainerTripleCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
