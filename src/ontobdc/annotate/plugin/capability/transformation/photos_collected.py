from pathlib import Path
from typing import Any, Dict, List, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.storage.adapter.media_type import MediaTypeResolver
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.domain.model.view import AnnotationView
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

        dataset_path: Optional[Path] = EntityDatasets.first(container_path, Annotation.ENTITY_IRI)
        photos: Dict[str, Dict[str, Any]] = {}
        left_out: List[Dict[str, str]] = []
        for item in items:
            item["photos"] = []
            # The first photo of an item is the document it was made on, with its geometries drawn on it: the geometry
            # of the annotation, as its tab shows it. It is its own, even if the same file is another item's photo.
            if item["shapes"]:
                source: str = item["source"]
                kind: str = (MediaTypeResolver.of(Path(source).name) or "") if source else ""
                view: Optional[Path] = (
                    dataset_path / "payload" / "document" / AnnotationView.file_name(item["global_id"])
                    if dataset_path is not None
                    else None
                )
                if kind.startswith("image/") and (container_path / source).is_file():
                    # An image is drawn on here, from the document itself.
                    key: str = f"{source}\u0000geometry\u0000{item['global_id']}"
                    photos[key] = {
                        "number": len(photos) + 1,
                        "path": source,
                        "name": f"{Path(source).stem}_geometry{Path(source).suffix}",
                        "items": [item["item"]],
                        "geometries": item["geometries"],
                    }
                    item["photos"].append(photos[key]["number"])
                elif view is not None and view.is_file():
                    # What cannot be drawn on here (a model in space, a page of a document) comes as the picture the person left it in, with the geometries already on it.
                    key = f"{source}\u0000view\u0000{item['global_id']}"
                    photos[key] = {
                        "number": len(photos) + 1,
                        "path": str(view.relative_to(container_path)),
                        "name": f"{Path(source).stem if source else item['global_id']}_geometry{AnnotationView.SUFFIX}",
                        "items": [item["item"]],
                    }
                    item["photos"].append(photos[key]["number"])
                elif source and kind.startswith("image/"):
                    left_out.append({"path": source, "reason": "not in the container"})
                else:
                    left_out.append({"path": source or item["global_id"], "reason": "the geometry is not on an image and its view was not kept: open it and close it to keep it"})
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
