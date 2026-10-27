from typing import Any, Dict, List, Optional, Tuple

from ontobdc.annotate.domain.model.geometry import WellKnownText


class GeometryDrawing:
    """
    The geometries of an annotation drawn on the image of the document it was made on, as the application shows them:
    each one in the colour and the width of its border and in the colour of its fill. Its coordinates are the share of
    the width and of the height of the image, from its top left corner, and its border is as wide as its width says, in
    the pixels of the image. Only what is flat can be drawn on an image: a line, several, a polygon.
    """

    FLAT: Tuple[str, ...] = ("LINESTRING", "MULTILINESTRING", "POLYGON")
    BORDER: str = "#000000"

    @classmethod
    def is_flat(cls, wkt: str) -> bool:
        try:
            kind, three, _ = WellKnownText.parse(wkt)
        except ValueError:
            return False

        return kind in cls.FLAT and not three

    @classmethod
    def draw(cls, image: Any, geometries: List[Dict[str, Any]]) -> None:
        """
        Draw the geometries on the image, which is changed.

        Raises:
            ImportError: Pillow is not installed.
        """
        from PIL import ImageDraw

        width, height = image.size
        pen: Any = ImageDraw.Draw(image)
        geometry: Dict[str, Any]
        for geometry in geometries:
            if not cls.is_flat(geometry["wkt"]):
                continue
            kind, _, tree = WellKnownText.parse(geometry["wkt"])
            color: str = geometry.get("stroke") or cls.BORDER
            size: int = max(1, round(float(geometry.get("stroke_width") or 1)))
            fill: Optional[str] = geometry.get("fill")
            outlines: List[List[Tuple[float, float]]] = [
                [(x * width, y * height) for x, y in outline]
                for outline in ([tree] if kind == "LINESTRING" else tree)
            ]
            if kind == "POLYGON" and fill:
                pen.polygon(outlines[0], fill=fill)
            for outline in outlines:
                pen.line(outline, fill=color, width=size, joint="curve")
