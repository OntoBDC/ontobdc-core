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


class AnnotationMoveGeometryCommand(CliCommandPort):
    """
    Move a geometry of an annotation the container already keeps.

    The annotation is the one whose global id ``--guid`` gives and the geometry the one whose identifier
    ``--move-geometry`` gives (the entity tells it, as the identifier of each geometry). ``--by`` is how far every point
    of it is moved: one number for each coordinate, separated by commas (``0.1,-0.05``, and a third in three dimensions).
    Its size and shape stay as they were. It is written by the machine that changes the geometries of an annotation,
    through the entity repository the context carries; OntoBDC has no default one, so without it this fails.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="annotate_move_geometry",
        logical_component="annotate",
        description="Move a geometry of an annotation, by its global id and the identifier of the geometry.",
        arguments=[
            {
                "accepts": ["--guid"],
                "valued": True,
                "parameter": Request.GUID_KEY,
                "description": "Global id of the annotation whose geometry is moved.",
                "type": "str",
                "usage": "ontobdc annotate --guid <id> --move-geometry <geometry id> --by <dx,dy[,dz]> [--container <id>]",
            },
            {
                "accepts": ["--move-geometry"],
                "valued": True,
                "parameter": Request.TARGET_KEY,
                "description": "Identifier of the geometry to move.",
                "type": "str",
            },
            {
                "accepts": ["--by"],
                "valued": True,
                "parameter": Request.OFFSET_KEY,
                "description": "How far to move it: one number for each coordinate, separated by commas.",
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
    REQUIRED_FLAGS: ClassVar[List[str]] = ["--guid", "--move-geometry", "--by"]
    OPTIONAL_FLAGS: ClassVar[List[str]] = ["--container"]

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != AnnotationMoveGeometryCommand.COMPONENT:
            return False

        return AnnotationMoveGeometryCommand._matches(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        return self._matches(self._request.command_args)

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        # Before anything is changed for a geometry that could not be kept.
        ContainerEntityRepository.provide(context)
        EntityWriteRequest.repository(context)
        context.set_parameter_value(Request.OPERATION_KEY, Request.MOVE_OPERATION)

        return AnnotationGeometrySaveStateTransitionHandler(context).execute()

    @staticmethod
    def _matches(scoped_args: List[str]) -> bool:
        """
        Report whether these scoped args are --guid, --move-geometry and --by, optionally --container, each with a value,
        in any order and none repeated.
        """
        if len(scoped_args) % 2 != 0:
            return False

        flags: List[str] = scoped_args[0::2]
        values: List[str] = scoped_args[1::2]
        allowed: List[str] = AnnotationMoveGeometryCommand.REQUIRED_FLAGS + AnnotationMoveGeometryCommand.OPTIONAL_FLAGS
        if len(set(flags)) != len(flags) or any(flag not in allowed for flag in flags):
            return False
        if any(flag not in flags for flag in AnnotationMoveGeometryCommand.REQUIRED_FLAGS):
            return False

        # A negative offset starts with "-", which a value may: only another flag starts with "--".
        return all(value.strip() and not value.startswith("--") for value in values)
