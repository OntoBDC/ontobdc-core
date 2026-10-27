from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
import shutil

from ontobdc.annotate.adapter.excel_workbook import (
    AnnotationWorkbook,
    ExportedItem,
    ExportedPhoto,
)
from ontobdc.annotate.plugin.machine.annotation_export_to_excel.etl import (
    AnnotationExportToExcelEtlEvent,
)
from ontobdc.annotate.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class WorkbookBuiltCapability(TransactionCapability):
    """
    Build the workbook and write it next to the ETL files of the export:
    the index of the annotations, the archive of the photos, and the
    carousel sheet of each photo of each item, with the reduced images
    embedded. The reduced images are removed afterwards, since the workbook
    holds them.

    Raises:
        ImportError: openpyxl or Pillow is not installed.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "workbook_built"
        ),
        version="1.0.0",
        name="Workbook Built",
        description=(
            "Build the Excel workbook of the annotations, embedding the reduced photos."
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
        group: Dict[str, str] = context.get_parameter_value(Request.GROUP_KEY)
        items: List[Dict[str, Any]] = context.get_parameter_value(Request.ITEMS_KEY)
        listed: List[Dict[str, Any]] = context.get_parameter_value(Request.PHOTOS_KEY)

        photos: Dict[int, ExportedPhoto] = {
            photo["number"]: ExportedPhoto(
                number=photo["number"],
                path=photo["path"],
                name=photo["name"],
                items=list(photo["items"]),
                image_path=Path(photo["image_path"]),
                thumbnail_path=Path(photo["thumbnail_path"]),
                image_size=tuple(photo["image_size"]),
                thumbnail_size=tuple(photo["thumbnail_size"]),
            )
            for photo in listed
        }
        exported: List[ExportedItem] = [
            ExportedItem(
                item=item["item"],
                global_id=item["global_id"],
                title=item["title"],
                text=item["text"],
                author=item["author"],
                created_at=item["created_at"],
                completed_at=item.get("completed_at", ""),
                photos=[photos[number] for number in item["photos"]],
            )
            for item in items
        ]
        workbook: Any = AnnotationWorkbook(
            container_name=group["container"],
            group_label=group["label"],
            items=exported,
            photos=list(photos.values()),
            language=group["language"],
        ).build()

        directory: Path = AnnotationExportToExcelEtlEvent.directory(container_path)
        target: Path = directory / AnnotationExportToExcelEtlEvent.WORKBOOK_FILE_NAME
        directory.mkdir(parents=True, exist_ok=True)
        workbook.save(str(target))
        shutil.rmtree(directory / AnnotationExportToExcelEtlEvent.PHOTOS_DIRECTORY_NAME, ignore_errors=True)

        context.set_parameter_value(Request.WORKBOOK_KEY, str(target))
        return {"workbook_path": str(target), "sheets": list(workbook.sheetnames)}
