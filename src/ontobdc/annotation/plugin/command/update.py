from pathlib import Path
from typing import Any, ClassVar, Dict, List

from rdflib import URIRef

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotation.adapter.store import AnnotationStore
from ontobdc.annotation.domain.model.annotation import Annotation
from ontobdc.annotation.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability,
)


class AnnotationUpdateCommand(CliCommandPort):
    """
    Change the data of an annotation the container already keeps.

    The annotation is the one whose global id ``--guid`` gives. Only what the
    command is told to change changes: the rest of the annotation, its
    creation time, its points and its base document included, stays as it
    was. It is written back through the model and the entity repository the
    context carries, like a new annotation; OntoBDC has no default
    repository, so without one this fails, before anything is read.

    ``--related`` replaces the related documents with the files it names.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_update",
        logical_component="annotation",
        description="Change the data of an annotation, by its global id.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": "annotation_guid",
                "description": "Global id of the annotation to change.",
                "type": "str",
                "usage": (
                    'ontobdc annotation --guid <id> [--type "<type>"] '
                    '[--title "<title>"] [--text "<text>"] [--author "<author>"] '
                    "[--related <file>]... [--container <id>]"
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
                "accepts": ["--type"],
                "valued": True,
                "parameter": "annotation_type",
                "description": "New type of the annotation.",
                "type": "str",
            },
            {
                "accepts": ["--title"],
                "valued": True,
                "parameter": "annotation_title",
                "description": "New title of the annotation.",
                "type": "str",
            },
            {
                "accepts": ["--text"],
                "valued": True,
                "parameter": "annotation_text",
                "description": "New text of the annotation.",
                "type": "str",
            },
            {
                "accepts": ["--author"],
                "valued": True,
                "parameter": "annotation_author",
                "description": "New author of the annotation.",
                "type": "str",
            },
            {
                "accepts": ["--related"],
                "valued": True,
                "description": (
                    "File of the container the annotation refers to; repeat "
                    "it for each file. They replace the related documents."
                ),
                "type": "Path",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotation"
    GUID_FLAG: ClassVar[str] = "--guid"
    RELATED_FLAG: ClassVar[str] = "--related"
    CHANGE_FLAGS: ClassVar[List[str]] = ["--type", "--title", "--text", "--author", "--related"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--container"]
    GUID_KEY: ClassVar[str] = "annotation_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    FIELD_BY_FLAG: ClassVar[Dict[str, str]] = {
        "--type": "annotation_type",
        "--title": "annotation_title",
        "--text": "annotation_text",
        "--author": "annotation_author",
    }

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation update at the CLI routing stage.
        """
        if not args or args[0] != AnnotationUpdateCommand.COMPONENT:
            return False

        return AnnotationUpdateCommand._matches(args[1:])

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
        stored: Dict[str, str] = AnnotationStore(repository, container_path).row(guid)

        annotation: Annotation = Annotation.from_record(stored)
        changes: Dict[str, Any] = self._changes(context, container_path)
        updated: Annotation = Annotation.model_validate(
            {**annotation.model_dump(), **changes}
        )
        updated.save(context, str(container_path))

        return CommandResponse(
            title="Annotation Updated",
            description=f"Changed {', '.join(sorted(changes)) or 'nothing'} of the annotation {guid}.",
            content={
                "global_id": updated.global_id,
                "changed": sorted(changes),
                "annotation_type": updated.annotation_type,
                "title": updated.title,
            },
        )

    def _changes(self, context: Any, container_path: Path) -> Dict[str, Any]:
        """
        The fields of the annotation the arguments change, by model field.
        """
        flags: List[str] = self._request.command_args[0::2]
        changes: Dict[str, Any] = {}

        if "--type" in flags:
            changes["annotation_type"] = AnnotationTypeIdentifiedCapability.identifier_of(
                AnnotationTypeIdentifiedCapability.annotation_type_iri(context)
            )
        for flag, field in (
            ("--title", "title"),
            ("--text", "text"),
            ("--author", "author"),
        ):
            if flag in flags:
                changes[field] = RequiredParameter.of(context, self.FIELD_BY_FLAG[flag])
        if self.RELATED_FLAG in flags:
            changes["related_documents"] = [
                str(ContainerDocumentIri.of(container_path, self._existing_file(path)))
                for path in self._related_paths()
            ]

        return changes

    def _related_paths(self) -> List[str]:
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
        Report whether these scoped args are --guid, at least one of the
        fields to change, and optionally --container, each with a value, in
        any order. Only --related may be repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = (
            [AnnotationUpdateCommand.GUID_FLAG]
            + AnnotationUpdateCommand.CHANGE_FLAGS
            + AnnotationUpdateCommand.OPTIONAL_FLAGS
        )
        singles: List[str] = [
            flag for flag in flags if flag != AnnotationUpdateCommand.RELATED_FLAG
        ]
        if len(set(singles)) != len(singles) or any(flag not in allowed for flag in flags):
            return False
        if AnnotationUpdateCommand.GUID_FLAG not in flags:
            return False
        if not any(flag in flags for flag in AnnotationUpdateCommand.CHANGE_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
