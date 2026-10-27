from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from ontobdc.annotate.domain.model.geometry import AnnotationGeometry
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.adapter.entity_geometry import EntityGeometries, EntityGeometry
from ontobdc.container.plugin.machine.entity_write.machine import (
    EntityWriteRequest,
    EntityWriteStateTransitionHandler,
)


class Annotation(BaseModel):
    """
    Something said about a place in a document.

    Its geometries are the places it was made at: points, lines, polygons or
    meshes, in two or three dimensions, as well-known text. They are not in
    its row but in the triples of its dataset (``EntityGeometries``).

    The model knows the shape an annotation is persisted in (the row the
    annotation facade declares) and writes itself through the entity writing
    machine, which finds or creates the dataset of annotations and hands the
    row to the repository the caller injected. It never knows where or how
    the rows are kept.
    """

    # Within one cell of the data source: a valid IRI never carries a bare "|".
    RELATED_SEPARATOR: ClassVar[str] = "|"

    ENTITY_IRI: ClassVar[str] = (
        "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl#Annotation"
    )

    global_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    annotation_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: Optional[str] = None
    geometries: List[AnnotationGeometry] = Field(default_factory=list)
    source_document: Optional[str] = None
    related_documents: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now().replace(microsecond=0))
    completed_at: Optional[datetime] = None
    # The other cells of its row, such as its tags: what the model does not know it does not own, and keeps as it was.
    extra: Dict[str, str] = Field(default_factory=dict)

    @field_validator("title", "annotation_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")

        return value.strip()

    @field_validator("related_documents")
    @classmethod
    def _related_iris(cls, value: List[str]) -> List[str]:
        related: List[str] = []
        iri: str
        for iri in value:
            stripped: str = iri.strip()
            if not stripped or cls.RELATED_SEPARATOR in stripped:
                raise ValueError(
                    f"a related document must be an IRI without '{cls.RELATED_SEPARATOR}'"
                )
            if stripped not in related:
                related.append(stripped)

        return related

    def to_record(self) -> Dict[str, Any]:
        """
        The row of this annotation: facade field identifier to value.
        """
        record: Dict[str, Any] = {
            **self.extra,
            "global_id": self.global_id,
            "annotation_type": self.annotation_type,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
        }
        if self.source_document is not None:
            record["source_document"] = self.source_document
        if self.related_documents:
            record["related_documents"] = self.RELATED_SEPARATOR.join(
                self.related_documents
            )
        if self.text is not None:
            record["text"] = self.text
        if self.author is not None:
            record["author"] = self.author
        if self.completed_at is not None:
            record["completed_at"] = self.completed_at.isoformat()

        return record

    @classmethod
    def from_record(cls, record: Dict[str, str], geometries: List[EntityGeometry]) -> "Annotation":
        """
        The annotation a row of the data source states: the inverse of
        ``to_record``. A cell the row leaves empty is an absent value.

        The geometries are not in the row but beside it: the caller gives the ones it read.

        Raises:
            ValueError: the row does not state a valid annotation, or one of its geometries is not
                the well-known text of a geometry an annotation can have.
        """
        def cell(name: str) -> Optional[str]:
            value: str = (record.get(name) or "").strip()
            return value or None

        related: Optional[str] = cell("related_documents")
        known: set = set(cls.model_fields) - {"extra"} | {"geometry"}
        return cls(
            extra={name: value for name, value in record.items() if name not in known and value},
            global_id=cell("global_id") or "",
            annotation_type=cell("annotation_type") or "",
            title=cell("title") or "",
            text=cell("text"),
            geometries=[AnnotationGeometry.of(geometry) for geometry in geometries],
            source_document=cell("source_document"),
            related_documents=related.split(cls.RELATED_SEPARATOR) if related else [],
            author=cell("author"),
            created_at=datetime.fromisoformat(cell("created_at") or ""),
            completed_at=datetime.fromisoformat(cell("completed_at")) if cell("completed_at") else None,
        )

    @classmethod
    def save_all(
        cls,
        annotations: List["Annotation"],
        context: CliContextPort,
        container_path: str,
    ) -> CommandResponse:
        """
        Write the annotations into the dataset of annotations of the container.

        The repository of the data source is the one the context carries under
        ``entity_repository``; OntoBDC has no default one, so without it the
        writing fails with ``EntityRepositoryNotInjectedError``.
        """
        keys: List[str] = [
            EntityWriteRequest.CONTAINER_PATH_KEY,
            EntityWriteRequest.ENTITY_IRI_KEY,
            EntityWriteRequest.RECORDS_KEY,
            EntityWriteRequest.SOURCE_DOCUMENTS_KEY,
            EntityWriteRequest.DATASET_PATH_KEY,
        ]
        context.set_parameter_value(EntityWriteRequest.CONTAINER_PATH_KEY, container_path)
        context.set_parameter_value(EntityWriteRequest.ENTITY_IRI_KEY, cls.ENTITY_IRI)
        context.set_parameter_value(
            EntityWriteRequest.RECORDS_KEY,
            [annotation.to_record() for annotation in annotations],
        )
        context.set_parameter_value(
            EntityWriteRequest.SOURCE_DOCUMENTS_KEY,
            sorted(
                {
                    annotation.source_document
                    for annotation in annotations
                    if annotation.source_document is not None
                }
            ),
        )
        try:
            response: CommandResponse = EntityWriteStateTransitionHandler(context).execute()
            # The row is written: the geometries go beside it. Writing both is not one step: when this one fails,
            # the annotation has its row and the geometries it had before.
            dataset_path: Path = Path(str(response.content["dataset_path"]))
            for annotation in annotations:
                EntityGeometries.write(
                    dataset_path,
                    annotation.global_id,
                    [geometry.kept() for geometry in annotation.geometries],
                )
            return response
        finally:
            key: str
            for key in keys:
                context.delete_parameter(key)

    def save(self, context: CliContextPort, container_path: str) -> CommandResponse:
        return type(self).save_all([self], context, container_path)
