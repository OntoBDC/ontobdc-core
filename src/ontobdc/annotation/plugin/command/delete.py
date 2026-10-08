from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotation.adapter.store import AnnotationStore


class AnnotationDeleteCommand(CliCommandPort):
    """
    Remove an annotation the container keeps.

    The annotation is the one whose global id ``--guid`` gives. Its row is
    removed from the data source through the entity repository the context
    carries; OntoBDC has no default one, so without it this fails, before
    anything is read. The documents it referred to are left alone.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_delete",
        logical_component="annotation",
        description="Remove an annotation, by its global id.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "annotation_guid",
                "description": "Global id of the annotation to remove.",
                "type": "str",
                "usage": "ontobdc annotation --guid <id> --delete [--container <id>]",
            },
            {
                "accepts": ["--delete"],
                "description": "Remove the annotation.",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container that keeps the annotation, by "
                    "storage identifier. When omitted, the container is "
                    "resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotation"
    GUID_FLAG: ClassVar[str] = "--guid"
    DELETE_FLAG: ClassVar[str] = "--delete"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    GUID_KEY: ClassVar[str] = "annotation_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation delete at the CLI routing stage.
        """
        if not args or args[0] != AnnotationDeleteCommand.COMPONENT:
            return False

        return AnnotationDeleteCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        # Before anything is read of an annotation that could not be removed.
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        guid: str = RequiredParameter.of(context, self.GUID_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()

        store: AnnotationStore = AnnotationStore(repository, container_path)
        stored: Dict[str, str] = store.row(guid)
        store.delete(guid)

        return CommandResponse(
            title="Annotation Deleted",
            description=f"Removed the annotation {guid}.",
            content={
                "global_id": guid,
                "annotation_type": stored.get("annotation_type", ""),
                "title": stored.get("title", ""),
            },
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid with a value, --delete
        with none, and optionally --container with a value, in any order.
        """
        if AnnotationDeleteCommand.DELETE_FLAG not in scoped_args:
            return False

        remaining: List[str] = [
            argument
            for argument in scoped_args
            if argument != AnnotationDeleteCommand.DELETE_FLAG
        ]
        if len(remaining) % 2 != 0 or len(remaining) != len(scoped_args) - 1:
            return False

        flags: List[str] = remaining[0::2]
        values: List[str] = remaining[1::2]
        allowed: List[List[str]] = [
            [AnnotationDeleteCommand.GUID_FLAG],
            sorted([AnnotationDeleteCommand.GUID_FLAG, AnnotationDeleteCommand.CONTAINER_FLAG]),
        ]
        if sorted(flags) not in allowed:
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
