import math
import re
from typing import Any, ClassVar, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from ontobdc.container.adapter.entity_geometry import EntityGeometry


class AnnotationPoint(BaseModel):
    """
    A point of an annotation, in the coordinates of the document it was made on.
    A point has a ``z`` when the document is in three dimensions.
    """

    x: float
    y: float
    z: Optional[float] = None


class WellKnownText:
    """
    The well-known text of the geometries an annotation can have, read and written in one form.

    A geometry is a ``POINT``, a ``LINESTRING`` (or several, a ``MULTILINESTRING``), a ``POLYGON``, a ``MULTIPOLYGON``, or a mesh: a ``TIN`` (triangles) or a
    ``POLYHEDRALSURFACE`` (faces). Each one is in two dimensions, or in three when its name is followed by ``Z`` and each of
    its coordinates has a third number. What is read is checked for its structure (the parentheses, the number of the
    coordinates of each point, the rings and the triangles closed), not for its topology, and written back in one form:
    ``POLYGON Z (((0 0 0, 1 0 0, 1 1 0, 0 0 0)))``.
    """

    #: How deep the groups of a kind are: a point has one, a polygon two (its rings), and a mesh three (its faces).
    DEPTH: ClassVar[Dict[str, int]] = {
        "POINT": 1,
        "LINESTRING": 1,
        "MULTILINESTRING": 2,
        "POLYGON": 2,
        "MULTIPOLYGON": 3,
        "TIN": 3,
        "POLYHEDRALSURFACE": 3,
    }
    HEADER: ClassVar["re.Pattern[str]"] = re.compile(r"^\s*([A-Za-z]+)(\s+Z)?\s*(\(.*\))\s*$", re.DOTALL)
    TOKEN: ClassVar["re.Pattern[str]"] = re.compile(r"\s*(\(|\)|,|[^\s(),]+)")

    @classmethod
    def parse(cls, text: str) -> Tuple[str, bool, Any]:
        """
        The kind, whether it has a Z, and the coordinates of the geometry, nested as the text nests them: the
        coordinates of a point are the numbers of a list, and each group of the text is a list.

        Raises:
            ValueError: the text is not the well-known text of a geometry of a kind an annotation can have.
        """
        match = cls.HEADER.match(text)
        if match is None:
            raise ValueError(f"unsupported geometry: {text!r}")

        kind: str = match.group(1).upper()
        three: bool = match.group(2) is not None
        if kind not in cls.DEPTH:
            raise ValueError(f"unsupported geometry: {text!r}")

        tokens: List[str] = [token.group(1) for token in cls.TOKEN.finditer(match.group(3))]
        position: int = 0

        def group(depth: int) -> List[Any]:
            nonlocal position
            if position >= len(tokens) or tokens[position] != "(":
                raise ValueError(f"unsupported geometry: {text!r}")
            position += 1

            items: List[Any] = []
            while True:
                if depth > 1:
                    items.append(group(depth - 1))
                else:
                    coordinates: List[float] = []
                    while position < len(tokens) and tokens[position] not in ("(", ")", ","):
                        try:
                            number: float = float(tokens[position])
                        except ValueError as error:
                            raise ValueError(f"unsupported geometry: {text!r}") from error
                        if not math.isfinite(number):
                            raise ValueError(f"unsupported geometry: {text!r}")
                        coordinates.append(number)
                        position += 1
                    items.append(coordinates)

                if position < len(tokens) and tokens[position] == ",":
                    position += 1
                    continue
                if position < len(tokens) and tokens[position] == ")":
                    position += 1
                    return items
                raise ValueError(f"unsupported geometry: {text!r}")

        coordinates_tree: List[Any] = group(cls.DEPTH[kind])
        if position != len(tokens):
            raise ValueError(f"unsupported geometry: {text!r}")

        cls._check(kind, three, coordinates_tree, text)
        return kind, three, coordinates_tree

    @classmethod
    def _check(cls, kind: str, three: bool, tree: List[Any], text: str) -> None:
        width: int = 3 if three else 2
        points: List[List[float]] = list(cls._points(tree, cls.DEPTH[kind]))
        if not points or any(len(point) != width for point in points):
            raise ValueError(f"the coordinates of {text!r} are not all of {width} numbers")

        rings: List[List[List[float]]] = [] if kind == "MULTILINESTRING" else list(cls._rings(tree, cls.DEPTH[kind]))
        if kind == "MULTILINESTRING" and any(len(line) < 2 for line in tree):
            raise ValueError(f"a line of {text!r} has at least two points")
        if kind == "POINT" and len(points) != 1:
            raise ValueError(f"a POINT has one point: {text!r}")
        if kind == "LINESTRING" and len(points) < 2:
            raise ValueError(f"a LINESTRING has at least two points: {text!r}")
        for ring in rings:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError(f"a ring of {text!r} is not closed, or has fewer than three points")
            if kind == "TIN" and len(ring) != 4:
                raise ValueError(f"a triangle of {text!r} has three points")
        if kind == "TIN" and any(len(face) != 1 for face in tree):
            raise ValueError(f"a triangle of {text!r} has no holes")

    @classmethod
    def _points(cls, tree: Any, depth: int) -> Iterable[List[float]]:
        if depth == 1:
            yield from tree
            return
        for item in tree:
            yield from cls._points(item, depth - 1)

    @classmethod
    def _rings(cls, tree: Any, depth: int) -> Iterable[List[List[float]]]:
        if depth <= 1:
            return
        if depth == 2:
            yield from tree
            return
        for item in tree:
            yield from cls._rings(item, depth - 1)

    @classmethod
    def write(cls, kind: str, three: bool, tree: List[Any]) -> str:
        """The text of a geometry, in the one form it is written in."""
        def number(value: float) -> str:
            return format(value, ".15g")

        def text(item: Any, depth: int) -> str:
            if depth == 1:
                return "(" + ", ".join(" ".join(number(value) for value in point) for point in item) + ")"
            return "(" + ", ".join(text(inner, depth - 1) for inner in item) + ")"

        return f"{kind}{' Z' if three else ''} {text(tree, cls.DEPTH[kind])}"

    @classmethod
    def translate(cls, text: str, offset: List[float]) -> str:
        """
        The same geometry, every point of it moved by the offset: one number for each coordinate of the points.

        Raises:
            ValueError: the offset has not as many numbers as the points have coordinates.
        """
        kind, three, tree = cls.parse(text)
        width: int = 3 if three else 2
        if len(offset) != width:
            raise ValueError(f"a geometry of {width} dimensions is moved by {width} numbers, not {len(offset)}")

        def moved(item: Any, depth: int) -> Any:
            if depth == 1:
                return [[value + by for value, by in zip(point, offset)] for point in item]
            return [moved(inner, depth - 1) for inner in item]

        return cls.write(kind, three, moved(tree, cls.DEPTH[kind]))

    @classmethod
    def dimension(cls, text: str) -> int:
        """Two or three: the number of the coordinates of each point."""
        return 3 if cls.parse(text)[1] else 2


class AnnotationGeometry(BaseModel):
    """
    One geometry of an annotation, in the coordinates of the document it was made on: a point, a line, a polygon or a
    mesh, in two or three dimensions, as its well-known text.
    """

    # Stays with the geometry while the others of its annotation come and go: how a person points at it.
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    wkt: str
    # The shape it was made as, such as a circle, when it was made as one: a polygon of 32 sides says no more than that.
    shape: Optional[str] = None
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    fill: Optional[str] = None

    COLOR: ClassVar["re.Pattern[str]"] = re.compile(r"^#[0-9a-fA-F]{6}$")

    @field_validator("stroke", "fill")
    @classmethod
    def _colour(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and cls.COLOR.match(value) is None:
            raise ValueError(f"a colour is #rrggbb, not {value!r}")

        return value.lower() if value is not None else None

    @field_validator("stroke_width")
    @classmethod
    def _width(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not (math.isfinite(value) and value > 0):
            raise ValueError(f"the width of a border is a number above zero, not {value!r}")

        return value

    @field_validator("wkt")
    @classmethod
    def _well_known(cls, value: str) -> str:
        kind, three, tree = WellKnownText.parse(value)
        return WellKnownText.write(kind, three, tree)

    @classmethod
    def of(cls, geometry: EntityGeometry) -> "AnnotationGeometry":
        """The geometry the dataset keeps, as an annotation has it."""
        return cls(id=geometry.id, wkt=geometry.wkt, shape=geometry.shape, stroke=geometry.stroke, stroke_width=geometry.stroke_width, fill=geometry.fill)

    def kept(self) -> EntityGeometry:
        """The geometry as the dataset keeps it."""
        return EntityGeometry(self.id, self.wkt, self.stroke, self.stroke_width, self.fill, self.shape)

    @property
    def kind(self) -> str:
        return WellKnownText.parse(self.wkt)[0]

    @property
    def dimension(self) -> int:
        return WellKnownText.dimension(self.wkt)

    @property
    def vertices(self) -> int:
        kind, _, tree = WellKnownText.parse(self.wkt)
        return len(list(WellKnownText._points(tree, WellKnownText.DEPTH[kind])))

    @classmethod
    def from_points(cls, points: Iterable[Union[AnnotationPoint, Mapping[str, Any]]]) -> "AnnotationGeometry":
        """
        The geometry of the points picked on a document, in click order: a POINT for one, a LINESTRING for more. It is
        in three dimensions when every point has a z.
        """
        picked: List[AnnotationPoint] = [
            point if isinstance(point, AnnotationPoint) else AnnotationPoint.model_validate(dict(point))
            for point in points
        ]
        if not picked:
            raise ValueError("a geometry of points needs at least one point")

        three: bool = all(point.z is not None for point in picked)
        coordinates: List[List[float]] = [
            [point.x, point.y, *([point.z] if three and point.z is not None else [])] for point in picked
        ]
        return cls(wkt=WellKnownText.write("POINT" if len(coordinates) == 1 else "LINESTRING", three, [coordinates[0]] if len(coordinates) == 1 else coordinates))
