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


class AnnotationStyleGeometryCommand(CliCommandPort):
    """
    Change how a geometry of an annotation the container already keeps is drawn.

    The annotation is the one whose global id ``--guid`` gives and the geometry the one whose identifier
    ``--style-geometry`` gives (the entity tells it, as the identifier of each geometry). ``--stroke`` and ``--fill`` are
    colours as ``#rrggbb`` (a fill of ``none`` takes the fill off) and ``--stroke-width`` a number above zero; what is
    not given stays as it was, and at least one is given. Its place and shape do not change. It is written by the machine
    that changes the geometries of an annotation, through the entity repository the context carries; OntoBDC has no
    default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_style_geometry",
        logical_component="annotate",
        description="Change how a geometry of an annotation is drawn, by its global id and the identifier of the geometry.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": Request.GUID_KEY,
                "description": "Global id of the annotation whose geometry is restyled.",
                "type": "str",
                "usage": "ontobdc annotate --guid <id> --style-geometry <geometry id> [--stroke <#rrggbb>] [--stroke-width <number>] [--fill <#rrggbb|none>] [--container <id>]",
            },
            {
                "accepts": ["--style-geometry"],
                "valued": True,
                "parameter": Request.TARGET_KEY,
                "description": "Identifier of the geometry to restyle.",
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
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--guid", "--style-geometry"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--stroke", "--stroke-width", "--fill", "--container"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != AnnotationStyleGeometryCommand.COMPONENT:
            return False

        return AnnotationStyleGeometryCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        # Before anything is changed for a geometry that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)
        context.set_parameter_value(Request.OPERATION_KEY, Request.STYLE_OPERATION)

        return AnnotationGeometrySaveStateTransitionHandler(context).execute()

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid and --style-geometry, optionally --stroke, --stroke-width, --fill and --container, each with a value,
        in any order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = AnnotationStyleGeometryCommand.REQUIRED_FLAGS + AnnotationStyleGeometryCommand.OPTIONAL_FLAGS
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in AnnotationStyleGeometryCommand.REQUIRED_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
