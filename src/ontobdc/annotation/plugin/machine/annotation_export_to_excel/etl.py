import json
from pathlib import Path
from typing import Any, ClassVar, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.etl import EtlDirectoryContract
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from ontobdc.annotation.plugin.machine.annotation_creation_from_point.etl import (
    AnnotationCreationFromPointEtlEvent,
)
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelProcessStatePort,
    AnnotationExportToExcelRequestPort,
)


class AnnotationExportToExcelEtlEvent:
    """
    The ETL file every state of the annotation export to Excel leaves::

        <container>/.__ontobdc__/etl/annotation/export/excel/<state>.json

    The container is the one whose annotations are exported. What the export
    builds on the way (the workbook) is kept next to those files.
    """

    ETL_MODULE_NAME: ClassVar[str] = "annotation"
    ETL_PHASE_NAME: ClassVar[str] = "export"
    ETL_ENTITY_NAME: ClassVar[str] = "excel"
    WORKBOOK_FILE_NAME: ClassVar[str] = "export.xlsx"
    PHOTOS_DIRECTORY_NAME: ClassVar[str] = "photos"

    @classmethod
    def container_of(cls, context: CliContextPort) -> Path:
        return Path(
            RequiredParameter.of(context, AnnotationExportToExcelRequestPort.CONTAINER_KEY)
        ).expanduser().resolve()

    @classmethod
    def directory(cls, container_path: Path) -> Path:
        return (
            StorageBootstrap.get_ontobdc_directory(container_path)
            / EtlDirectoryContract.DIRECTORY_NAME
            / cls.ETL_MODULE_NAME
            / cls.ETL_PHASE_NAME
            / cls.ETL_ENTITY_NAME
        )

    @classmethod
    def path(
        cls,
        container_path: Path,
        state: AnnotationExportToExcelProcessStatePort,
    ) -> Path:
        return cls.directory(container_path) / f"{state.value}.json"

    @classmethod
    def write(
        cls,
        container_path: Path,
        state: AnnotationExportToExcelProcessStatePort,
        result: Dict[str, Any],
    ) -> Path:
        target: Path = cls.path(container_path, state)
        AnnotationCreationFromPointEtlEvent.write_text(
            target,
            json.dumps(
                {
                    "state": state.value,
                    "phase": cls.ETL_PHASE_NAME,
                    "entity": cls.ETL_ENTITY_NAME,
                    "result": result,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=lambda value: f"<{type(value).__name__}>",
            ),
        )
        return target
