from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ontobdc.shared.domain.model.draw import (
    DrawSource,
    DrawSourceKind,
)
from ontobdc.shared.domain.port.draw import DrawSourceStrategyPort


class RasterDrawSourceStrategy(DrawSourceStrategyPort):
    """Recognize raster sources through Pillow's content decoders."""

    priority: int = 100

    def accepts(self, source_path: Path) -> bool:
        try:
            with Image.open(source_path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError):
            return False
        return True

    def load(self, source_path: Path) -> DrawSource:
        with Image.open(source_path) as image:
            source_format: str = str(image.format or "RASTER").upper()
            normalized_image: Image.Image = image.convert("RGBA")
            width: int = normalized_image.width
            height: int = normalized_image.height
            output: BytesIO = BytesIO()
            normalized_image.save(output, format="PNG")

        return DrawSource(
            kind=DrawSourceKind.RASTER,
            source_format=source_format,
            content_format="PNG",
            content=output.getvalue(),
            width=width,
            height=height,
        )
