from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class AnnotationsCollectedCapability(TransactionCapability):
    """
    Read the annotations of the identified type from the container, oldest
    first, and number them (``01``, ``02``, ...). The files each refers to
    are kept as paths in the container, not as the IRIs the row holds.
    The annotations are read through the entity repository the context
    carries; OntoBDC has no default one, so without it this fails.

    Raises:
        LookupError: the container keeps no annotation of that type.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "annotations_collected"
        ),
        version="1.0.0",
        name="Annotations Collected",
        description=(
            "Read and number the annotations of the identified type kept by the container."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "export", "excel"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
    )

    def label(self, lang: str = "en") -> str:
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        container_path: Path = Path(
            RequiredParameter.of(context, Request.CONTAINER_KEY)
        ).expanduser().resolve()
        group: Dict[str, str] = context.get_parameter_value(Request.GROUP_KEY)

        dataset_path: Optional[Path] = EntityDatasets.first(container_path, Annotation.ENTITY_IRI)
        rows: List[Dict[str, str]] = []
        if dataset_path is not None and repository.data_source_exists(dataset_path):
            rows = [
                row
                for row in repository.rows(dataset_path).values()
                if row.get("annotation_type", "") == group["identifier"]
            ]
        if not rows:
            raise LookupError(
                f"The container keeps no annotation of type '{group['identifier']}' to export."
            )

        rows.sort(key=lambda row: (row.get("created_at", ""), row.get("title", "")))
        width: int = max(2, len(str(len(rows))))
        items: List[Dict[str, Any]] = [
            {
                "item": f"{position:0{width}d}",
                "global_id": row.get("global_id", ""),
                "title": row.get("title", ""),
                "text": row.get("text", ""),
                "author": row.get("author", ""),
                "created_at": row.get("created_at", ""),
                "completed_at": row.get("completed_at", ""),
                "related": [
                    path
                    for path in (
                        ContainerDocumentIri.path_of(container_path, iri) or ""
                        for iri in row.get("related_documents", "").split(
                            Annotation.RELATED_SEPARATOR
                        )
                        if iri
                    )
                    if path
                ],
            }
            for position, row in enumerate(rows, start=1)
        ]
        context.set_parameter_value(Request.ITEMS_KEY, items)
        return {
            "count": len(items),
            "items": [
                {"item": item["item"], "global_id": item["global_id"], "title": item["title"]}
                for item in items
            ],
        }
