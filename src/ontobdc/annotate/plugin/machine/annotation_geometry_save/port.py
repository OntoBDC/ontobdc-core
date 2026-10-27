from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.response.command import CommandResponse


class AnnotationGeometrySaveProcessStatePort(str, Enum):
    """
    Base enum contract for the states of the saving of a shape on an annotation.
    """


class AnnotationGeometrySaveRequestPort:
    """
    Canonical context keys of the change of the geometries of an annotation: the annotation and what is done to them (a
    shape put, a geometry moved or taken off); for a shape, the shape and its arguments and how it is drawn.
    """

    OPERATION_KEY: ClassVar[str] = "geometry_operation"
    SHAPE_OPERATION: ClassVar[str] = "shape"
    MOVE_OPERATION: ClassVar[str] = "move"
    DELETE_OPERATION: ClassVar[str] = "delete"
    STYLE_OPERATION: ClassVar[str] = "style"
    RESTORE_OPERATION: ClassVar[str] = "restore"
    WKT_KEY: ClassVar[str] = "geometry_wkt"
    POSITION_KEY: ClassVar[str] = "geometry_position"
    NO_FILL: ClassVar[str] = "none"
    TARGET_KEY: ClassVar[str] = "geometry_target"
    OFFSET_KEY: ClassVar[str] = "geometry_offset"
    GUID_KEY: ClassVar[str] = "annotation_guid"
    CONTAINER_KEY: ClassVar[str] = "container_path"
    SHAPE_KEY: ClassVar[str] = "shape_name"
    ARGUMENTS_KEY: ClassVar[str] = "shape_arguments"
    STROKE_KEY: ClassVar[str] = "geometry_stroke"
    STROKE_WIDTH_KEY: ClassVar[str] = "geometry_stroke_width"
    FILL_KEY: ClassVar[str] = "geometry_fill"
    GEOMETRIES_KEY: ClassVar[str] = "annotation_geometries"
    SAVED_KEY: ClassVar[str] = "geometry_saved_count"


class AnnotationGeometrySaveStateTransitionHandlerPort(ABC):
    @abstractmethod
    def execute(self) -> CommandResponse:
        """
        Change the geometries of the annotation as asked and keep them.
        """
        ...
