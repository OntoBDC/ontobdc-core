from typing import Any, ClassVar, List

from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.plugin.machine.annotation_geometry_save.machine import (
    AnnotationGeometrySaveStateTransitionHandler,
)
from ontobdc.annotate.plugin.machine.annotation_geometry_save.port import AnnotationGeometrySaveRequestPort as Request


class AnnotationRestoreGeometryCommand(CliCommandPort):
    """
    Put back a geometry that was taken off an annotation the container already keeps.

    The annotation is the one whose global id ``--guid`` gives. ``--restore-geometry`` is the identifier the geometry had,
    ``--wkt`` its well-known text and ``--position`` where it was among the geometries of the annotation (what is above
    it is drawn over it); ``--shape``, ``--stroke``, ``--stroke-width`` and ``--fill`` are what it was made as and how it
    was drawn. It is what undoes taking a geometry off. It is written by the machine that changes the geometries of an
    annotation, through the entity repository the context carries; OntoBDC has no default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_restore_geometry",
        logical_component="annotate",
        description="Put back a geometry of an annotation, by its global id, with its identifier, its text and its place in the list.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": Request.GUID_KEY,
                "description": "Global id of the annotation the geometry is put back on.",
                "type": "str",
                "usage": "ontobdc annotate --guid <id> --restore-geometry <geometry id> --wkt <text> --position <n> [--shape <name>] [--stroke <#rrggbb>] [--stroke-width <number>] [--fill <#rrggbb|none>] [--container <id>]",
            },
            {
                "accepts": ["--restore-geometry"],
                "valued": True,
                "parameter": Request.TARGET_KEY,
                "description": "Identifier the geometry had.",
                "type": "str",
            },
            {
                "accepts": ["--wkt"],
                "valued": True,
                "parameter": Request.WKT_KEY,
                "description": "Well-known text of the geometry.",
                "type": "str",
            },
            {
                "accepts": ["--position"],
                "valued": True,
                "parameter": Request.POSITION_KEY,
                "description": "Where it was among the geometries of the annotation, from zero.",
                "type": "str",
            },
            {
                "accepts": ["--shape"],
                "valued": True,
                "parameter": Request.SHAPE_KEY,
                "description": "The shape it was made as, when it was made as one.",
                "type": "str",
            },
            {
                "accepts": ["--stroke"],
                "valued": True,
                "parameter": Request.STROKE_KEY,
                "description": "Colour of the border, as #rrggbb.",
                "type": "str",
            },
            {
                "accepts": ["--stroke-width"],
                "valued": True,
                "parameter": Request.STROKE_WIDTH_KEY,
                "description": "Width of the border, a number above zero.",
                "type": "str",
            },
            {
                "accepts": ["--fill"],
                "valued": True,
                "parameter": Request.FILL_KEY,
                "description": "Colour of the fill, as #rrggbb, or none for no fill.",
                "type": "str",
            },
            {
                "accepts": ["--container"],
                "valued": True,
                "parameter": Request.CONTAINER_KEY,
                "description": (
                    "Select the container that keeps the annotation, by storage identifier. When omitted, the "
                    "container is resolved from the current working directory."
                ),
                "type": "str",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "annotate"
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--guid", "--restore-geometry", "--wkt", "--position"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--shape", "--stroke", "--stroke-width", "--fill", "--container"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != AnnotationRestoreGeometryCommand.COMPONENT:
            return False

        return AnnotationRestoreGeometryCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        # Before anything is changed for a geometry that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)
        context.set_parameter_value(Request.OPERATION_KEY, Request.RESTORE_OPERATION)

        return AnnotationGeometrySaveStateTransitionHandler(context).execute()

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid, --restore-geometry, --wkt and --position, optionally --shape, --stroke, --stroke-width, --fill and --container, each with a value,
        in any order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = AnnotationRestoreGeometryCommand.REQUIRED_FLAGS + AnnotationRestoreGeometryCommand.OPTIONAL_FLAGS
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in AnnotationRestoreGeometryCommand.REQUIRED_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
