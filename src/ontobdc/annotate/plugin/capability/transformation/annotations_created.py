from pathlib import Path
from typing import Any, Dict, List

from rdflib import URIRef

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability,
)
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.port import (
    AnnotationDetailsRequestPort,
    DrawableDocumentRequestPort,
)


class AnnotationsCreatedCapability(TransactionCapability):
    """
    Create the annotation at the points that were captured, and persist it.

    The type comes from the identification of the type, the points from the
    capture, the title, text and author from the details that were asked for,
    and the document it was made on is the file of the request, as a document
    of the container that holds it. The annotation writes itself through the
    repository the caller injected into the context as ``entity_repository``;
    without one, this fails.
    """

    POINTS_KEY: str = "captured_points"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "annotations_created"
        ),
        version="1.0.0",
        name="Annotations Created",
        description=(
            "Create the annotation of the identified type at the captured "
            "points and persist it in the annotations dataset of the "
            "container that holds the file."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "create", "persist"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                "file_open_path": {"type": "string", "required": True},
                POINTS_KEY: {"type": "array", "required": True},
                AnnotationDetailsRequestPort.TITLE_KEY: {"type": "string", "required": True},
            },
        },
        output_schema={"properties": {}},
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Anotações criadas"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        file_path: Path = Path(
            RequiredParameter.of(context, DrawableDocumentRequestPort.PATH_KEY)
        ).expanduser().resolve()
        container_path: Path = ContainerDocumentIri.container_of(file_path)
        annotation_type: URIRef = AnnotationTypeIdentifiedCapability.annotation_type_iri(
            context
        )

        points: Any = context.get_parameter_value(self.POINTS_KEY)
        if not isinstance(points, list) or not points:
            raise ValueError(f"'{self.POINTS_KEY}' must be a list of points, not empty.")

        annotation: Annotation = Annotation(
            annotation_type=AnnotationTypeIdentifiedCapability.identifier_of(
                annotation_type
            ),
            title=RequiredParameter.of(context, AnnotationDetailsRequestPort.TITLE_KEY),
            text=RequiredParameter.optional(context, AnnotationDetailsRequestPort.TEXT_KEY),
            author=RequiredParameter.optional(
                context, AnnotationDetailsRequestPort.AUTHOR_KEY
            ),
            points=points,
            source_document=str(ContainerDocumentIri.of(container_path, file_path)),
        )
        response: Any = annotation.save(context, str(container_path))

        return {
            "global_id": annotation.global_id,
            "annotation_type_iri": str(annotation_type),
            "source_document": annotation.source_document,
            "dataset_path": response.content["dataset_path"],
        }
