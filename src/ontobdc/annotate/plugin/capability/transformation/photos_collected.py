from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.media_type import MediaTypeResolver
from ontobdc.annotate.plugin.machine.annotation_export_to_excel.port import (
    AnnotationExportToExcelRequestPort as Request,
)


class PhotosCollectedCapability(TransactionCapability):
    """
    Find, among the files each annotation refers to, the images the
    container holds, and number them in the order they are first met. A file
    that several annotations refer to is one photo with several items. A
    related file that is not an image, or is no longer in the container, is
    left out and named in the result.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "photos_collected"
        ),
        version="1.0.0",
        name="Photos Collected",
        description=(
            "Find and number the images among the files the annotations refer to."
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
        items: List[Dict[str, Any]] = context.get_parameter_value(Request.ITEMS_KEY)

        photos: Dict[str, Dict[str, Any]] = {}
        left_out: List[Dict[str, str]] = []
        for item in items:
            item["photos"] = []
            for path in item["related"]:
                media_type: str = MediaTypeResolver.of(Path(path).name) or ""
                if not media_type.startswith("image/"):
                    left_out.append({"path": path, "reason": "not an image"})
                    continue
                if not (container_path / path).is_file():
                    left_out.append({"path": path, "reason": "not in the container"})
                    continue
                if path not in photos:
                    photos[path] = {
                        "number": len(photos) + 1,
                        "path": path,
                        "name": Path(path).name,
                        "items": [],
                    }
                if item["item"] not in photos[path]["items"]:
                    photos[path]["items"].append(item["item"])
                item["photos"].append(photos[path]["number"])

        listed: List[Dict[str, Any]] = list(photos.values())
        context.set_parameter_value(Request.ITEMS_KEY, items)
        context.set_parameter_value(Request.PHOTOS_KEY, listed)
        return {"count": len(listed), "photos": listed, "left_out": left_out}
