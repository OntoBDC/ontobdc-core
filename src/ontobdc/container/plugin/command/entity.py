from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.entity_listing import ContainerEntities


class ContainerEntityCommand(CliCommandPort):
    """
    Command for listing the entities a registered container holds.

    The entities are listed dataset by dataset, for every dataset the
    container registers.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="ct_entity",
        logical_component="container",
        description="List the entities of a registered container.",
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
                "description": (
                    "List every entity the container holds, grouped by the "
                    "dataset that keeps it."
                ),
                "usage": "ontobdc container --entity [--container <id-or-path>]",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "container"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the container entity listing at the CLI routing stage.
        """
        if not args or args[0] != ContainerEntityCommand.COMPONENT:
            return False

        return ContainerEntityCommand._matches(args[1:])

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
        Report whether these scoped args are --entity with an optional
        --container <id-or-path>.
        """
        if ContainerEntityCommand.ENTITY_FLAG not in scoped_args:
            return False

        remaining: List[str] = list(scoped_args)
        remaining.remove(ContainerEntityCommand.ENTITY_FLAG)
        if not remaining:
            return True

        return (
            len(remaining) == 2
            and remaining[0] == ContainerEntityCommand.CONTAINER_FLAG
            and bool(remaining[1].strip())
        )

    def run(self) -> CommandResponse:
        """
        List the entities of every dataset of the selected container.
        """
        container_path: Path = Path(
            RequiredParameter.of(self._request.context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        datasets: List[Dict[str, Any]] = ContainerEntities.of(container_path)
        count: int = sum(len(dataset["entities"]) for dataset in datasets)

        return CommandResponse(
            title="Container Entities",
            description=(
                f"{count} entities in {len(datasets)} datasets of the "
                f"container «{container_path.name}»."
            ),
            content={"datasets": datasets},
        )
