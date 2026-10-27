from typing import Any, Dict, List, Mapping

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from pathlib import Path

from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.adapter.store import AnnotationStore
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.domain.model.geometry import AnnotationGeometry
from ontobdc.annotate.plugin.machine.annotation_geometry_save.port import AnnotationGeometrySaveRequestPort as Request
from ontobdc.annotate.plugin.machine.annotation_geometry_save.state import AnnotationGeometrySaveProcessState


class GeometrySavedCapability(TransactionCapability):
    """
    Keep the geometries the annotation has once what was asked is done.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "geometry_saved"
        ),
        version="1.0.0",
        name="Geometry Saved",
        description="Keep the geometries the annotation has once what was asked is done.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "geometry", "persist"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The geometries were kept on the annotation."},
            "debug_entry": {"en": "Working on: Geometry Saved."},
        },
    )

    def label(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_SAVED.label(lang)

    def description(self, lang: str = "en") -> str:
        return AnnotationGeometrySaveProcessState.GEOMETRY_SAVED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        guid: str = RequiredParameter.of(context, Request.GUID_KEY)
        container_path: Path = Path(RequiredParameter.of(context, Request.CONTAINER_KEY)).expanduser().resolve()
        made: List[Dict[str, Any]] = context.get_parameter_value(Request.GEOMETRIES_KEY)

        annotation: Annotation = AnnotationStore(EntityWriteRequest.repository(context), container_path).annotation(guid)
        updated: Annotation = Annotation.model_validate(
            {**annotation.model_dump(), "geometries": [AnnotationGeometry.model_validate(geometry) for geometry in made]}
        )
        updated.save(context, str(container_path))

        return {
            "resulting_state": AnnotationGeometrySaveProcessState.GEOMETRY_SAVED,
            "global_id": guid,
            "geometries": len(made),
        }
