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
from ontobdc.annotation.domain.model.annotation import Annotation


class AnnotationClearCommand(CliCommandPort):
    """
    Empty optional fields of an annotation the container already keeps.

    The annotation is the one whose global id ``--guid`` gives, and each
    ``--clear`` names a field to empty: ``text``, ``author`` or ``related``
    (the related documents). What an annotation cannot do without, such as its
    title, its type and the place it was made, is not clearable. The rest of
    the annotation stays as it was. It is written back through the model and
    the entity repository the context carries; OntoBDC has no default one, so
    without it this fails, before anything is read.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_clear",
        logical_component="annotation",
        description="Empty optional fields of an annotation, by its global id.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "annotation_guid",
                "description": "Global id of the annotation to change.",
                "type": "str",
                "usage": (
                    "ontobdc annotation --guid <id> --clear <text|author|related>... "
                    "[--container <id>]"
                ),
            },
            {
                "accepts": ["--clear"],
                "valued": True,
                "description": (
                    "Field to empty: text, author or related. Repeat it for "
                    "each field."
                ),
                "type": "str",
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
    CLEAR_FLAG: ClassVar[str] = "--clear"
    CONTAINER_FLAG: ClassVar[str] = "--container"
    GUID_KEY: ClassVar[str] = "annotation_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    # What --clear names, and what it empties in the model.
    EMPTY_BY_FIELD: ClassVar[Dict[str, Any]] = {
        "text": ("text", None),
        "author": ("author", None),
        "related": ("related_documents", []),
    }

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation clear at the CLI routing stage.
        """
        if not args or args[0] != AnnotationClearCommand.COMPONENT:
            return False

        return AnnotationClearCommand._matches(args[1:])

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
        # Before anything is read of an annotation that could not be kept.
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        guid: str = RequiredParameter.of(context, self.GUID_KEY)
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        fields: List[str] = self._fields()

        annotation: Annotation = Annotation.from_record(
            AnnotationStore(repository, container_path).row(guid)
        )
        emptied: Dict[str, Any] = dict(self.EMPTY_BY_FIELD[field] for field in fields)
        updated: Annotation = Annotation.model_validate(
            {**annotation.model_dump(), **emptied}
        )
        updated.save(context, str(container_path))

        return CommandResponse(
            title="Annotation Cleared",
            description=f"Emptied {', '.join(fields)} of the annotation {guid}.",
            content={"global_id": updated.global_id, "cleared": fields},
        )

    def _fields(self) -> List[str]:
        """
        The fields every --clear names, in the order given, none twice.
        """
        args: List[str] = self._request.command_args
        fields: List[str] = []
        for position in range(0, len(args), 2):
            if args[position] == self.CLEAR_FLAG and args[position + 1] not in fields:
                fields.append(args[position + 1])

        return fields

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid, at least one --clear
        naming a field that can be emptied, and optionally --container, each
        with a value, in any order. Only --clear may be repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        singles: List[str] = [
            flag for flag in flags if flag != AnnotationClearCommand.CLEAR_FLAG
        ]
        if sorted(singles) not in (
            [AnnotationClearCommand.GUID_FLAG],
            sorted([AnnotationClearCommand.GUID_FLAG, AnnotationClearCommand.CONTAINER_FLAG]),
        ):
            return False
        if AnnotationClearCommand.CLEAR_FLAG not in flags:
            return False
        if not all(value.strip() and not value.startswith("--") for value in values):
            return False

        return all(
            value in AnnotationClearCommand.EMPTY_BY_FIELD
            for flag, value in zip(flags, values)
            if flag == AnnotationClearCommand.CLEAR_FLAG
        )
