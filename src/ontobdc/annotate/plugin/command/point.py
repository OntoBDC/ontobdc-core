from typing import Any, ClassVar, Dict, List

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.machine import (
    AnnotationCreationFromPointStateTransitionHandler,
)


class AnnotationCreationFromPointCommand(CliCommandPort):
    """
    Create an annotation of a given type at points picked on a drawing.

    The parameter stage binds the type and the file; the command runs the
    annotation creation from point machine, which owns everything from the
    identification of the type to the annotation persisted in the dataset of
    the container that holds the file.

    OntoBDC knows no viewer and no storage for the annotations: the
    capabilities that open the file and ask for the points, and the
    repository that keeps the rows, come from whoever runs this command (the
    context carries them). Without them it fails, naming what is missing.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_creation_from_point",
        logical_component="annotate",
        description=(
            "Create an annotation of a given type at points picked on a drawing."
        ),
        arguments=[
            {
                "accepts": ["--type"],
                "valued": True,
                "parameter": "annotation_type",
                "description": (
                    "Type of the annotation, by its IRI or by a label or "
                    "identifier in any language, such as note, issue or "
                    "question."
                ),
                "type": "str",
            },
            {
                "accepts": ["--point"],
                "valued": True,
                "parameter": "file_open_path",
                "description": "Drawing on which the annotation points are picked.",
                "type": "Path",
                "usage": (
                    'ontobdc annotation --type "<type>" --point <drawing>'
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    VALUED_FLAGS: ClassVar[List[str]] = ["--type", "--point"]
    TYPE_KEY: ClassVar[str] = "annotation_type"
    FILE_KEY: ClassVar[str] = "file_open_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation creation from point at the CLI routing stage.
        """
        if not args or args[0] != AnnotationCreationFromPointCommand.COMPONENT:
            return False

        return AnnotationCreationFromPointCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        """
        Run the annotation creation from point machine on the prepared context.
        """
        context: Any = self._request.context
        # Before anyone is made to pick points that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)
        annotation_type: str = RequiredParameter.of(context, self.TYPE_KEY)
        drawing: str = RequiredParameter.of(context, self.FILE_KEY)
        result: Dict[str, Any] = AnnotationCreationFromPointStateTransitionHandler(
            context
        ).execute()
        return CommandResponse(
            title="Annotation Created",
            description=f"Created a {annotation_type} annotation on {drawing}.",
            content={
                "annotation_type": annotation_type,
                "drawing": drawing,
                "global_id": result["global_id"],
                "annotation_type_iri": result["annotation_type_iri"],
                "source_document": result["source_document"],
                "dataset_path": result["dataset_path"],
            },
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --type and --point, each with a
        value, in any order.
        """
        flags: List[str] = AnnotationCreationFromPointCommand.VALUED_FLAGS
        if len(scoped_args) != 2 * len(flags):
            return False

        seen: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        if sorted(seen) != sorted(flags):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
