from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.annotation.adapter.types import AnnotationTypes
from ontobdc.annotation.plugin.capability.transformation.annotation_type_identified import (
    AnnotationTypeIdentifiedCapability,
)
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class ExportScopeIdentifiedCapability(TransactionCapability):
    """
    Identify what the export covers: the annotation type, named by a
    parameter of the context as its IRI or by any label or identifier, and
    the container whose annotations are exported. The label of the type in
    the language of the export, and the name of the container (the project),
    are kept for the workbook.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "export_scope_identified"
        ),
        version="1.0.0",
        name="Export Scope Identified",
        description=(
            "Resolve the annotation type to export and the container that keeps its annotations."
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
        container_path: Path = Path(
            RequiredParameter.of(context, Request.CONTAINER_KEY)
        ).expanduser().resolve()
        language: str = (
            RequiredParameter.optional(context, Request.LANGUAGE_KEY) or "en"
        ).strip().lower().replace("_", "-")

        annotation_type: Any = AnnotationTypeIdentifiedCapability.annotation_type_iri(context)
        identifier: str = AnnotationTypeIdentifiedCapability.identifier_of(annotation_type)
        labels: Dict[str, str] = next(
            (
                declared["labels"]
                for declared in AnnotationTypes.all()
                if declared["iri"] == str(annotation_type)
            ),
            {},
        )
        label: str = labels.get(language) or labels.get(language.split("-")[0]) or labels.get("en") or identifier

        group: Dict[str, str] = {
            "iri": str(annotation_type),
            "identifier": identifier,
            "label": label,
            "project": container_path.name,
            "language": language,
        }
        context.set_parameter_value(Request.GROUP_KEY, group)
        return {"group": group, "container_path": str(container_path)}
