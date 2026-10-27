from typing import Any, ClassVar, Dict, List

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


class AnnotationShapeCommand(CliCommandPort):
    """
    Put a shape on an annotation the container already keeps.

    The annotation is the one whose global id ``--guid`` gives, and the shape is made into geometries (a rectangle, a
    circle, an amoeba or a cross on a flat document; a box, a cylinder, a sphere or a lollipop in space) that are kept
    after the ones it has. Each ``--param`` is a number of the shape, ``name=value``; ``--stroke`` and ``--fill`` are
    colours as ``#rrggbb`` and ``--stroke-width`` a number above zero. The saving is a machine of its own, written
    through the entity repository the context carries; OntoBDC has no default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_shape",
        logical_component="annotate",
        description="Put a shape on an annotation, by its global id.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": Request.GUID_KEY,
                "description": "Global id of the annotation to put the shape on.",
                "type": "str",
                "usage": (
                    "ontobdc annotation --guid <id> --shape <name> [--param <name>=<value>]... "
                    "[--stroke <#rrggbb>] [--stroke-width <number>] [--fill <#rrggbb>] [--container <id>]"
                ),
            },
            {
                "accepts": ["--shape"],
                "valued": True,
                "parameter": Request.SHAPE_KEY,
                "description": "Shape to put: rectangle, circle, amoeba, cross, box, cylinder, sphere or lollipop.",
                "type": "str",
            },
            {
                "accepts": ["--param"],
                "valued": True,
                "description": "A number of the shape as name=value, such as radius=2. Repeat it for each.",
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
                "description": "Colour of the fill, as #rrggbb.",
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
    PARAM_FLAG: ClassVar[str] = "--param"
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--guid", "--shape"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--stroke", "--stroke-width", "--fill", "--container"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the annotation shape at the CLI routing stage.
        """
        if not args or args[0] != AnnotationShapeCommand.COMPONENT:
            return False

        return AnnotationShapeCommand._matches(args[1:])

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
        # Before anything is made for a shape that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)
        context.set_parameter_value(Request.OPERATION_KEY, Request.SHAPE_OPERATION)
        context.set_parameter_value(Request.ARGUMENTS_KEY, self._arguments())

        return AnnotationGeometrySaveStateTransitionHandler(context).execute()

    def _arguments(self) -> Dict[str, str]:
        """
        The numbers of the shape, by name, as every --param gives them.
        """
        args: List[str] = self._request.command_args
        arguments: Dict[str, str] = {}
        for position in range(0, len(args), 2):
            if args[position] != self.PARAM_FLAG:
                continue
            name, _, value = args[position + 1].partition("=")
            if not name or not value or name in arguments:
                raise ValueError(f"--param is name=value, once for each name: {args[position + 1]!r}")
            arguments[name] = value

        return arguments

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid and --shape, optionally --stroke, --stroke-width, --fill and
        --container, each with a value, in any order; --param may be repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        singles: List[str] = [flag for flag in flags if flag != AnnotationShapeCommand.PARAM_FLAG]
        allowed: List[str] = AnnotationShapeCommand.REQUIRED_FLAGS + AnnotationShapeCommand.OPTIONAL_FLAGS
        if len(set(singles)) != len(singles) or any(flag not in allowed for flag in singles):
            return False
        if any(flag not in flags for flag in AnnotationShapeCommand.REQUIRED_FLAGS):
            return False

        return all(value.strip() and not value.startswith("--") for value in values)
