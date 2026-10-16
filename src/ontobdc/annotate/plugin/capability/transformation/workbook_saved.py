from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
import shutil

from ontobdc.annotate.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class WorkbookSavedCapability(TransactionCapability):
    """
    Hand over the workbook: where the request asked for it (``export_output_path``),
    or where it was built. The result says where it is, relative to the
    container too, and how big it is.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "workbook_saved"
        ),
        version="1.0.0",
        name="Workbook Saved",
        description=(
            "Save the workbook where the request asked for it and report where it is."
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
        built: Path = Path(RequiredParameter.of(context, Request.WORKBOOK_KEY))
        requested: Optional[str] = RequiredParameter.optional(context, Request.OUTPUT_KEY)

        saved: Path = built
        if requested:
            saved = Path(requested).expanduser().resolve()
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(built, saved)
            built.unlink()

        try:
            relative: Optional[str] = saved.relative_to(container_path).as_posix()
        except ValueError:
            relative = None
        return {
            "path": str(saved),
            "relative_path": relative,
            "bytes": saved.stat().st_size,
            "items": len(context.get_parameter_value(Request.ITEMS_KEY)),
            "photos": len(context.get_parameter_value(Request.PHOTOS_KEY)),
        }
