from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from rdflib import URIRef

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability,
)


class AnnotationCreateCommand(CliCommandPort):
    """
    Create an annotation of a given type, with a title, on no document and at
    no point.

    The type is named by its IRI or by a label or identifier in any language,
    and is a note when none is given.
    The annotation is kept in the annotations dataset of the container, which
    is the one ``--container`` names or, without it, the one of the current
    directory. It is written through the entity repository the context
    carries; OntoBDC has no default one, so without it this fails, before
    anything is resolved.

    An annotation placed at points picked on a drawing is created by
    ``--type`` with ``--point`` instead.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_create",
        logical_component="annotate",
        description="Create an annotation of a given type, with a title.",
        arguments=[
            {
                "accepts": ["--type"],
                "valued": True,
                "parameter": "annotation_type",
                "description": (
                    "Type of the annotation, by its IRI or by a label or "
                    "identifier in any language, such as note, issue or "
                    "question. Optional: a note when omitted."
                ),
                "type": "str",
            },
            {
                "accepts": ["--title"],
                "valued": True,
                "parameter": "annotation_title",
                "description": "Title of the annotation.",
                "type": "str",
                "usage": (
                    'ontobdc annotation [--type "<type>"] --title "<title>" '
                    '[--text "<text>"] [--author "<author>"] [--completed-at <ISO-8601>] [--related <file>]... [--container <id>]'
                ),
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
            {
                "accepts": ["--related"],
                "valued": True,
                "description": (
                    "File of the container the annotation refers to, other "
                    "than the one it was made on. Optional; repeat it for "
                    "each file."
                ),
                "type": "Path",
            },
            {
                "accepts": ["--text"],
                "valued": True,
                "parameter": "annotation_text",
                "description": "Text of the annotation. Optional.",
                "type": "str",
            },
            {
                "accepts": ["--author"],
                "valued": True,
                "parameter": "annotation_author",
                "description": "Author of the annotation. Optional.",
                "type": "str",
            },
            {
                "accepts": ["--completed-at"],
                "valued": True,
                "parameter": "annotation_completed_at",
                "description": "Completion date and time in ISO 8601 format. Optional.",
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--title"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--type", "--text", "--author", "--completed-at", "--container"]
    RELATED_FLAG: ClassVar[str] = "--related"
    DEFAULT_TYPE: ClassVar[str] = "note"
    TYPE_KEY: ClassVar[str] = "annotation_type"
    TITLE_KEY: ClassVar[str] = "annotation_title"
    TEXT_KEY: ClassVar[str] = "annotation_text"
    AUTHOR_KEY: ClassVar[str] = "annotation_author"
    COMPLETED_AT_KEY: ClassVar[str] = "annotation_completed_at"
    CONTAINER_KEY: ClassVar[str] = "container_path"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation creation at the CLI routing stage.
        """
        if not args or args[0] != AnnotationCreateCommand.COMPONENT:
            return False

        return AnnotationCreateCommand._matches(args[1:])

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
        # Before anything is resolved for an annotation that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)

        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        if RequiredParameter.optional(context, self.TYPE_KEY) is None:
            context.set_parameter_value(self.TYPE_KEY, self.DEFAULT_TYPE)
        annotation_type: URIRef = AnnotationTypeIdentifiedCapability.annotation_type_iri(
            context
        )

        related_documents: List[str] = [
            str(ContainerDocumentIri.of(container_path, self._existing_file(path)))
            for path in self._related_paths()
        ]

        annotation: Annotation = Annotation(
            annotation_type=AnnotationTypeIdentifiedCapability.identifier_of(
                annotation_type
            ),
            title=RequiredParameter.of(context, self.TITLE_KEY),
            text=RequiredParameter.optional(context, self.TEXT_KEY),
            author=RequiredParameter.optional(context, self.AUTHOR_KEY),
            completed_at=RequiredParameter.optional(context, self.COMPLETED_AT_KEY),
            related_documents=related_documents,
        )
        response: Any = annotation.save(context, str(container_path))

        return CommandResponse(
            title="Annotation Created",
            description=f"Created a {annotation.annotation_type} annotation.",
            content={
                "annotation_type": annotation.annotation_type,
                "annotation_type_iri": str(annotation_type),
                "global_id": annotation.global_id,
                "title": annotation.title,
                "dataset_path": response.content["dataset_path"],
            },
        )

    def _related_paths(self) -> List[str]:
        """
        The value of every --related of the arguments, in the order given.
        """
        args: List[str] = self._request.command_args
        return [
            args[position + 1]
            for position in range(0, len(args), 2)
            if args[position] == self.RELATED_FLAG
        ]

    @staticmethod
    def _existing_file(path: str) -> Path:
        file_path: Path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"{file_path} is not a file.")

        return file_path

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --title, optionally --type,
        --text, --author and --container, each with a value, in any order and
        none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = (
            AnnotationCreateCommand.REQUIRED_FLAGS + AnnotationCreateCommand.OPTIONAL_FLAGS
        )
        singles: List[str] = [
            flag for flag in flags if flag != AnnotationCreateCommand.RELATED_FLAG
        ]
        if len(set(singles)) != len(singles):
            return False
        if any(
            flag not in allowed + [AnnotationCreateCommand.RELATED_FLAG]
            for flag in flags
        ):
            return False
        if any(flag not in flags for flag in AnnotationCreateCommand.REQUIRED_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
