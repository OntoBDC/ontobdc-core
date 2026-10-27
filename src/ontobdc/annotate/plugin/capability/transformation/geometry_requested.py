from typing import Any, Dict, List, Mapping

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from pathlib import Path

from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.adapter.store import AnnotationStore
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.domain.model.geometry import AnnotationGeometry, WellKnownText
from ontobdc.annotate.domain.model.offset import OffsetText
from ontobdc.annotate.domain.model.shape import AnnotationShape
from ontobdc.annotate.plugin.machine.annotation_geometry_save.port import AnnotationGeometrySaveRequestPort as Request
from ontobdc.annotate.plugin.machine.annotation_geometry_save.state import AnnotationGeometrySaveProcessState


class GeometryRequestedCapability(TransactionCapability):
    """
    Check that the annotation exists and that what is asked of its geometries can be done: a shape the application draws, a geometry it has.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "geometry_requested"
        ),
        version="1.0.0",
        name="Geometry Requested",
        description="Check that the annotation exists and that what is asked of its geometries can be done: a shape the application draws, a geometry it has.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "geometry", "shape"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The shape asked for on the annotation was understood."},
            "debug_entry": {"en": "Working on: Geometry Requested."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_REQUESTED.label(lang)

    def description(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_REQUESTED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        guid: str = RequiredParameter.of(context, Request.GUID_KEY)
        container_path: Path = Path(RequiredParameter.of(context, Request.CONTAINER_KEY)).expanduser().resolve()
        operation: str = RequiredParameter.of(context, Request.OPERATION_KEY)

        # The annotation has to be there before anything is made for it.
        annotation: Annotation = AnnotationStore(EntityWriteRequest.repository(context), container_path).annotation(guid)
        if operation == Request.SHAPE_OPERATION:
            shape: str = RequiredParameter.of(context, Request.SHAPE_KEY)
            if shape not in AnnotationShape.names():
                raise ValueError(f"unknown shape {shape!r}; the shapes are {', '.join(AnnotationShape.names())}")
            if not isinstance(context.get_parameter_value(Request.ARGUMENTS_KEY), Mapping):
                raise ValueError(f"'{Request.ARGUMENTS_KEY}' must be the arguments of the shape, by name.")
        elif operation == Request.RESTORE_OPERATION:
            target = RequiredParameter.of(context, Request.TARGET_KEY)
            if target in [geometry.id for geometry in annotation.geometries]:
                raise ValueError(f"The annotation {guid} already has the geometry {target}.")
            AnnotationGeometry(id=target, wkt=RequiredParameter.of(context, Request.WKT_KEY))
            if int(RequiredParameter.of(context, Request.POSITION_KEY)) < 0:
                raise ValueError("the position of a geometry is not below zero")
        elif operation in (Request.MOVE_OPERATION, Request.DELETE_OPERATION, Request.STYLE_OPERATION):
            target: str = RequiredParameter.of(context, Request.TARGET_KEY)
            if target not in [geometry.id for geometry in annotation.geometries]:
                raise LookupError(f"The annotation {guid} has no geometry {target}.")
            if operation == Request.STYLE_OPERATION and not any(
                RequiredParameter.optional(context, key) is not None
                for key in (Request.STROKE_KEY, Request.STROKE_WIDTH_KEY, Request.FILL_KEY)
            ):
                raise ValueError("the style of a geometry is changed by a colour, a width or a fill")
            if operation == Request.MOVE_OPERATION:
                WellKnownText.translate(
                    next(geometry.wkt for geometry in annotation.geometries if geometry.id == target),
                    OffsetText.numbers(RequiredParameter.of(context, Request.OFFSET_KEY)),
                )
        else:
            raise ValueError(f"unknown operation {operation!r} on the geometries of an annotation")

        return {
            "resulting_state": AnnotationGeometrySaveProcessState.GEOMETRY_REQUESTED,
            "annotation_guid": guid,
            "operation": operation,
        }
