from typing import Any, ClassVar, Dict, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.machine import (
    AnnotationExportToExcelStateTransitionHandler,
)


class AnnotationExportCommand(CliCommandPort):
    """
    Export the annotations of one type to a file.

    The only format is ``excel``: a workbook with the index of the
    annotations, the archive of the photos they refer to and a carousel sheet
    for each photo of each annotation, with the photos reduced to a light
    image. The work is the annotation export to Excel machine, a state at a
    time, each leaving its ETL file in the container. The annotations are
    read through the entity repository the context carries; OntoBDC has no
    default one, so without it this fails, before anything is read.

    Without ``--output`` the workbook is left with the ETL files of the
    export, and its path is in the response.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotation_export",
        logical_component="annotation",
        description="Export the annotations of one type, as an Excel workbook.",
        arguments=[
            {
                "accepts": ["--export"],
                "valued": True,
                "parameter": "export_format",
                "description": "Format of the export. The only one is: excel.",
                "type": "str",
                "usage": (
                    "ontobdc annotation --export excel --type <type> "
                    "[--output <file>] [--language <tag>] [--container <id>]"
                ),
            },
            {
                "accepts": ["--type"],
                "valued": True,
                "parameter": "annotation_type",
                "description": (
                    "Annotation type whose annotations are exported: its IRI, "
                    "or a label or identifier in any language."
                ),
                "type": "str",
            },
            {
                "accepts": ["--output"],
                "valued": True,
                "parameter": "export_output_path",
                "description": "Where to write the file. When omitted it is left with the ETL files.",
                "type": "Path",
            },
            {
                "accepts": ["--language"],
                "valued": True,
                "parameter": "export_language",
                "description": "Language of the words in the file (en, pt-br, es-es). Default: en.",
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": "container",
                "description": (
                    "Select the container whose annotations are exported, by "
                    "storage identifier. When omitted, the container is "
                    "resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotation"
    EXPORT_FLAG: ClassVar[str] = "--export"
    TYPE_FLAG: ClassVar[str] = "--type"
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--output", "--language", "--container"]
    FORMAT_KEY: ClassVar[str] = "export_format"
    FORMATS: ClassVar[List[str]] = ["excel"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation export at the CLI routing stage.
        """
        if not args or args[0] != AnnotationExportCommand.COMPONENT:
            return False

        return AnnotationExportCommand._matches(args[1:])

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
        # Before anything is read for an export that could not be made.
        EntityWriteRequest.repository(context)

        export_format: str = RequiredParameter.of(context, self.FORMAT_KEY).strip().lower()
        if export_format not in self.FORMATS:
            raise ValueError(
                f"'{export_format}' is not an export format. The formats are: "
                f"{', '.join(self.FORMATS)}."
            )

        result: Dict[str, Any] = AnnotationExportToExcelStateTransitionHandler(context).execute()
        return CommandResponse(
            title="Annotations Exported",
            description=(
                f"Exported {result['items']} annotations and {result['photos']} "
                f"photos to {export_format}."
            ),
            content={"format": export_format, **result},
        )

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --export and --type, optionally
        --output, --language and --container, each with a value, in any
        order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        required: List[str] = [
            AnnotationExportCommand.EXPORT_FLAG,
            AnnotationExportCommand.TYPE_FLAG,
        ]
        if len(set(flags)) != len(flags):
            return False
        if any(flag not in required + AnnotationExportCommand.OPTIONAL_FLAGS for flag in flags):
            return False
        if any(flag not in flags for flag in required):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
