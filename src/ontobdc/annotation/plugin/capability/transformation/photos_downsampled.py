from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.annotation.adapter.photo_downsampler import PhotoDownsampler
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.etl import (
    AnnotationExportToExcelEtlEvent,
)
from ontobdc.annotation.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class PhotosDownsampledCapability(TransactionCapability):
    """
    Reduce each photo to the images the workbook embeds: one of at most
    ``PhotoDownsampler.LONG_SIDE`` pixels for the carousel, and a small one
    for the photo archive. They are written next to the ETL files of the
    export, and removed once the workbook has been built. A photo Pillow
    cannot read is left out of the workbook and named in the result.

    Raises:
        ImportError: Pillow is not installed.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotation.plugin.capability.transformation.target."
            "photos_downsampled"
        ),
        version="1.0.0",
        name="Photos Downsampled",
        description=(
            "Reduce each photo to a light image to be embedded in the workbook."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "export", "excel", "photo"],
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
        photos: List[Dict[str, Any]] = context.get_parameter_value(Request.PHOTOS_KEY)
        items: List[Dict[str, Any]] = context.get_parameter_value(Request.ITEMS_KEY)
        directory: Path = (
            AnnotationExportToExcelEtlEvent.directory(container_path)
            / AnnotationExportToExcelEtlEvent.PHOTOS_DIRECTORY_NAME
        )

        kept: List[Dict[str, Any]] = []
        skipped: List[Dict[str, str]] = []
        original_bytes: int = 0
        reduced_bytes: int = 0
        for photo in photos:
            source: Path = container_path / photo["path"]
            image: Path = directory / f"{photo['number']:03d}.jpg"
            thumbnail: Path = directory / f"{photo['number']:03d}_thumbnail.jpg"
            try:
                photo["image_size"] = list(PhotoDownsampler.reduce(source, image))
                photo["thumbnail_size"] = list(
                    PhotoDownsampler.reduce(
                        source,
                        thumbnail,
                        PhotoDownsampler.THUMBNAIL_LONG_SIDE,
                        PhotoDownsampler.THUMBNAIL_QUALITY,
                    )
                )
            except OSError as error:
                skipped.append({"path": photo["path"], "reason": str(error)})
                continue
            photo["image_path"] = str(image)
            photo["thumbnail_path"] = str(thumbnail)
            original_bytes += source.stat().st_size
            reduced_bytes += image.stat().st_size + thumbnail.stat().st_size
            kept.append(photo)

        dropped: set = {photo["number"] for photo in photos} - {photo["number"] for photo in kept}
        for item in items:
            item["photos"] = [number for number in item["photos"] if number not in dropped]
        context.set_parameter_value(Request.PHOTOS_KEY, kept)
        context.set_parameter_value(Request.ITEMS_KEY, items)
        return {
            "count": len(kept),
            "long_side": PhotoDownsampler.LONG_SIDE,
            "quality": PhotoDownsampler.QUALITY,
            "original_bytes": original_bytes,
            "reduced_bytes": reduced_bytes,
            "skipped": skipped,
        }
