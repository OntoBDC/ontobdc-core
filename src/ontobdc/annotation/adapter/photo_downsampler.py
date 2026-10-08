from pathlib import Path
from typing import ClassVar, Tuple


class PhotoDownsampler:
    """
    Reduce a photograph to a JPEG that is light enough to be embedded in a
    workbook: its longest side is cut to a limit and it is saved with a
    fixed quality. The photograph is turned upright by its EXIF orientation,
    and one with transparency is laid on white.
    """

    LONG_SIDE: ClassVar[int] = 800
    QUALITY: ClassVar[int] = 70
    THUMBNAIL_LONG_SIDE: ClassVar[int] = 320
    THUMBNAIL_QUALITY: ClassVar[int] = 60

    @classmethod
    def reduce(
        cls,
        source: Path,
        target: Path,
        long_side: int = LONG_SIDE,
        quality: int = QUALITY,
    ) -> Tuple[int, int]:
        """
        Write the reduced photograph to ``target`` and return its size in
        pixels (width, height).

        Raises:
            ImportError: Pillow is not installed.
            OSError: the file is not an image Pillow can read.
        """
        from PIL import Image, ImageOps

        with Image.open(source) as opened:
            image: Image.Image = ImageOps.exif_transpose(opened)
            if image.mode in ("RGBA", "LA", "P"):
                converted: Image.Image = image.convert("RGBA")
                flattened: Image.Image = Image.new("RGB", converted.size, "white")
                flattened.paste(converted, mask=converted.getchannel("A"))
                image = flattened
            elif image.mode != "RGB":
                image = image.convert("RGB")
            image.thumbnail((long_side, long_side), Image.LANCZOS)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, "JPEG", quality=quality, optimize=True, progressive=True)
            return image.size
