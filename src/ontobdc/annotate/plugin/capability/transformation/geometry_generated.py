from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.adapter.store import AnnotationStore
from ontobdc.annotate.domain.model.geometry import AnnotationGeometry, WellKnownText
from ontobdc.annotate.domain.model.offset import OffsetText
from ontobdc.annotate.domain.model.shape import AnnotationShape
from ontobdc.annotate.plugin.machine.annotation_geometry_save.port import AnnotationGeometrySaveRequestPort as Request
from ontobdc.annotate.plugin.machine.annotation_geometry_save.state import AnnotationGeometrySaveProcessState


class GeometryGeneratedCapability(TransactionCapability):
    """
    Work out the geometries the annotation has once what is asked is done: a shape made into geometries and put after the others, a geometry moved, a geometry taken off.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "geometry_generated"
        ),
        version="1.0.0",
        name="Geometry Generated",
        description="Work out the geometries the annotation has once what is asked is done: a shape made into geometries and put after the others, a geometry moved, a geometry taken off.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "geometry", "shape", "wkt"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The shape was made into geometries."},
            "debug_entry": {"en": "Working on: Geometry Generated."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_GENERATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_GENERATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        guid: str = RequiredParameter.of(context, Request.GUID_KEY)
        container_path: Path = Path(RequiredParameter.of(context, Request.CONTAINER_KEY)).expanduser().resolve()
        operation: str = RequiredParameter.of(context, Request.OPERATION_KEY)
        current: List[AnnotationGeometry] = list(
            AnnotationStore(EntityWriteRequest.repository(context), container_path).annotation(guid).geometries
        )

        changed: int
        if operation == Request.SHAPE_OPERATION:
            shape: str = RequiredParameter.of(context, Request.SHAPE_KEY)
            width: Any = RequiredParameter.optional(context, Request.STROKE_WIDTH_KEY)
            added: List[AnnotationGeometry] = [
                AnnotationGeometry(
                    wkt=wkt,
                    shape=shape,
                    stroke=RequiredParameter.optional(context, Request.STROKE_KEY),
                    stroke_width=float(width) if width is not None else None,
                    fill=RequiredParameter.optional(context, Request.FILL_KEY),
                )
                for wkt in AnnotationShape.make(shape, context.get_parameter_value(Request.ARGUMENTS_KEY))
            ]
            result: List[AnnotationGeometry] = [*current, *added]
            changed = len(added)
        elif operation == Request.MOVE_OPERATION:
            target: str = RequiredParameter.of(context, Request.TARGET_KEY)
            offset: List[float] = OffsetText.numbers(RequiredParameter.of(context, Request.OFFSET_KEY))
            result = [
                geometry.model_copy(update={"wkt": WellKnownText.translate(geometry.wkt, offset)}) if geometry.id == target else geometry
                for geometry in current
            ]
            changed = 1
        elif operation == Request.RESTORE_OPERATION:
            width = RequiredParameter.optional(context, Request.STROKE_WIDTH_KEY)
            restored: AnnotationGeometry = AnnotationGeometry(
                id=RequiredParameter.of(context, Request.TARGET_KEY),
                wkt=RequiredParameter.of(context, Request.WKT_KEY),
                shape=RequiredParameter.optional(context, Request.SHAPE_KEY),
                stroke=RequiredParameter.optional(context, Request.STROKE_KEY),
                stroke_width=float(width) if width is not None else None,
                fill=RequiredParameter.optional(context, Request.FILL_KEY),
            )
            # Where it was in the list: what is above it is drawn over it.
            position: int = min(int(RequiredParameter.of(context, Request.POSITION_KEY)), len(current))
            result = [*current[:position], restored, *current[position:]]
            changed = 1
        elif operation == Request.STYLE_OPERATION:
            target = RequiredParameter.of(context, Request.TARGET_KEY)
            stroke: Any = RequiredParameter.optional(context, Request.STROKE_KEY)
            size: Any = RequiredParameter.optional(context, Request.STROKE_WIDTH_KEY)
            fill: Any = RequiredParameter.optional(context, Request.FILL_KEY)
            # Only what is given changes; a fill of none takes the fill off.
            updates: Dict[str, Any] = {
                **({"stroke": stroke} if stroke is not None else {}),
                **({"stroke_width": float(size)} if size is not None else {}),
                **({"fill": None if fill == Request.NO_FILL else fill} if fill is not None else {}),
            }
            result = [
                AnnotationGeometry.model_validate({**geometry.model_dump(), **updates}) if geometry.id == target else geometry
                for geometry in current
            ]
            changed = 1
        else:
            target = RequiredParameter.of(context, Request.TARGET_KEY)
            result = [geometry for geometry in current if geometry.id != target]
            changed = 1
        context.set_parameter_value(Request.GEOMETRIES_KEY, [geometry.model_dump() for geometry in result])
        context.set_parameter_value(Request.SAVED_KEY, changed)

        return {
            "resulting_state": AnnotationGeometrySaveProcessState.GEOMETRY_GENERATED,
            "changed": changed,
        }
