import math
from typing import Any, Callable, ClassVar, Dict, List, Mapping, Tuple

from ontobdc.annotate.domain.model.geometry import WellKnownText

Point = List[float]


class AnnotationShape:
    """
    The shapes a person can put on a document, each one made into the geometries that draw it.

    Well-known text has no circle and no sphere: a round shape is a polygon or a mesh of as many sides as the shape is
    given, and once made it is only that, the shape it came from is not kept. A shape is told by its name and by
    numbers, which come as text: the place it is at, its size, and for the few that need it how finely it is cut. The
    flat shapes are in two dimensions and the solid ones in three.

    - ``rectangle``: ``x``, ``y`` (its corner of least coordinates), ``width``, ``height``.
    - ``circle``: ``x``, ``y`` (its centre), ``radius``; ``segments`` (32), ``aspect`` (1).
    - ``amoeba``: ``points``, the control points ``x,y;x,y;...`` (at least three) a smooth closed outline goes through.
    - ``cross``: ``x``, ``y`` (its centre), ``size``; ``aspect`` (1); two lines, in one geometry.
    - ``box``: ``x``, ``y``, ``z`` (its centre), ``width`` (along x), ``depth`` (along y), ``height`` (along z).
    - ``cylinder``: ``x``, ``y``, ``z`` (its centre), ``radius``, ``height`` (along z); ``segments`` (24).
    - ``sphere``: ``x``, ``y``, ``z`` (its centre), ``radius``; ``rings`` (8), ``segments`` (16).
    - ``lollipop``: ``x``, ``y``, ``z`` (the tip of its stick), ``height`` (of the whole, along z), ``radius`` (of its
      ball, at the top); the stick is a cylinder and the ball a sphere, in one mesh.

    A shape is one geometry, whatever it is made of.

    A document whose coordinates are the share of its width (for x) and of its height (for y) is not as tall as it is
    wide: for the circle and the cross to look round and square on it, ``aspect`` is its width over its height, and
    their size, given in x, is that many times more in y.
    """

    SMOOTHING: ClassVar[int] = 8
    MAX_PARTS: ClassVar[int] = 256

    @classmethod
    def names(cls) -> List[str]:
        return list(cls._makers())

    @classmethod
    def make(cls, name: str, arguments: Mapping[str, str]) -> List[str]:
        """
        The well-known text of each geometry of the shape.

        Raises:
            ValueError: the shape is not one of these, or its arguments are missing, not numbers, or of a size that
                makes no shape.
        """
        makers: Dict[str, Callable[["AnnotationShape._Arguments"], List[str]]] = cls._makers()
        if name not in makers:
            raise ValueError(f"unknown shape {name!r}; the shapes are {', '.join(makers)}")

        return makers[name](cls._Arguments(name, arguments))

    class _Arguments:
        def __init__(self, shape: str, values: Mapping[str, str]) -> None:
            self._shape: str = shape
            self._values: Mapping[str, str] = values

        def text(self, name: str) -> str:
            if name not in self._values:
                raise ValueError(f"the shape {self._shape} needs {name}")

            return self._values[name]

        def number(self, name: str) -> float:
            text: str = self.text(name)
            try:
                value: float = float(text)
            except ValueError as error:
                raise ValueError(f"{name} of the shape {self._shape} is not a number: {text!r}") from error
            if not math.isfinite(value):
                raise ValueError(f"{name} of the shape {self._shape} is not a number: {text!r}")

            return value

        def size(self, name: str) -> float:
            value: float = self.number(name)
            if value <= 0:
                raise ValueError(f"{name} of the shape {self._shape} is above zero, not {value:g}")

            return value

        def size_or(self, name: str, default: float) -> float:
            return self.size(name) if name in self._values else default

        def count(self, name: str, default: int, least: int) -> int:
            if name not in self._values:
                return default
            value: float = self.number(name)
            if value != int(value) or not least <= value <= AnnotationShape.MAX_PARTS:
                raise ValueError(
                    f"{name} of the shape {self._shape} is a whole number from {least} to {AnnotationShape.MAX_PARTS}"
                )

            return int(value)

    @classmethod
    def _makers(cls) -> Dict[str, Callable[["AnnotationShape._Arguments"], List[str]]]:
        return {
            "rectangle": cls._rectangle,
            "circle": cls._circle,
            "amoeba": cls._amoeba,
            "cross": cls._cross,
            "box": cls._box,
            "cylinder": cls._cylinder,
            "sphere": cls._sphere,
            "lollipop": cls._lollipop,
        }

    @staticmethod
    def _polygon(ring: List[Point]) -> str:
        return WellKnownText.write("POLYGON", False, [[*ring, ring[0]]])

    @classmethod
    def _rectangle(cls, a: "AnnotationShape._Arguments") -> List[str]:
        x, y, width, height = a.number("x"), a.number("y"), a.size("width"), a.size("height")
        return [cls._polygon([[x, y], [x + width, y], [x + width, y + height], [x, y + height]])]

    @classmethod
    def _circle(cls, a: "AnnotationShape._Arguments") -> List[str]:
        x, y, radius, segments = a.number("x"), a.number("y"), a.size("radius"), a.count("segments", 32, 8)
        aspect: float = a.size_or("aspect", 1)
        return [
            cls._polygon(
                [
                    [
                        x + radius * math.cos(2 * math.pi * step / segments),
                        y + radius * aspect * math.sin(2 * math.pi * step / segments),
                    ]
                    for step in range(segments)
                ]
            )
        ]

    @classmethod
    def _amoeba(cls, a: "AnnotationShape._Arguments") -> List[str]:
        controls: List[Point] = []
        for pair in a.text("points").split(";"):
            try:
                x, y = (float(value) for value in pair.split(","))
            except ValueError as error:
                raise ValueError(f"points of the shape amoeba are x,y;x,y;...: {pair!r}") from error
            controls.append([x, y])
        if len(controls) < 3:
            raise ValueError("points of the shape amoeba are at least three")

        # A closed Catmull-Rom curve: it goes through every control point and is smooth at each.
        outline: List[Point] = []
        count: int = len(controls)
        for index in range(count):
            p0, p1, p2, p3 = (controls[(index + offset) % count] for offset in (-1, 0, 1, 2))
            for step in range(cls.SMOOTHING):
                t: float = step / cls.SMOOTHING
                outline.append(
                    [
                        0.5
                        * (
                            2 * p1[axis]
                            + (-p0[axis] + p2[axis]) * t
                            + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t * t
                            + (-p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]) * t * t * t
                        )
                        for axis in (0, 1)
                    ]
                )
        return [cls._polygon(outline)]

    @classmethod
    def _cross(cls, a: "AnnotationShape._Arguments") -> List[str]:
        x, y, half = a.number("x"), a.number("y"), a.size("size") / 2
        high: float = half * a.size_or("aspect", 1)
        return [
            WellKnownText.write(
                "MULTILINESTRING",
                False,
                [[[x - half, y - high], [x + half, y + high]], [[x - half, y + high], [x + half, y - high]]],
            )
        ]

    @staticmethod
    def _solid(faces: List[List[Point]]) -> str:
        return WellKnownText.write("POLYHEDRALSURFACE", True, [[[*face, face[0]]] for face in faces])

    @classmethod
    def _box_faces(cls, x: float, y: float, z: float, width: float, depth: float, height: float) -> List[List[Point]]:
        x0, x1, y0, y1, z0, z1 = x - width / 2, x + width / 2, y - depth / 2, y + depth / 2, z - height / 2, z + height / 2
        return [
            [[x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0]],
            [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
            [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]],
            [[x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]],
            [[x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]],
            [[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]],
        ]

    @classmethod
    def _box(cls, a: "AnnotationShape._Arguments") -> List[str]:
        return [cls._solid(cls._box_faces(a.number("x"), a.number("y"), a.number("z"), a.size("width"), a.size("depth"), a.size("height")))]

    @classmethod
    def _cylinder_faces(cls, x: float, y: float, z0: float, radius: float, height: float, segments: int) -> List[List[Point]]:
        angles: List[float] = [2 * math.pi * step / segments for step in range(segments)]
        bottom: List[Point] = [[x + radius * math.cos(angle), y + radius * math.sin(angle), z0] for angle in angles]
        top: List[Point] = [[px, py, z0 + height] for px, py, _ in bottom]
        faces: List[List[Point]] = [list(reversed(bottom)), top]
        for step in range(segments):
            following: int = (step + 1) % segments
            faces.append([bottom[step], bottom[following], top[following], top[step]])
        return faces

    @classmethod
    def _cylinder(cls, a: "AnnotationShape._Arguments") -> List[str]:
        height: float = a.size("height")
        return [
            cls._solid(
                cls._cylinder_faces(
                    a.number("x"), a.number("y"), a.number("z") - height / 2, a.size("radius"), height, a.count("segments", 24, 3)
                )
            )
        ]

    @classmethod
    def _sphere_triangles(cls, x: float, y: float, z: float, radius: float, rings: int, segments: int) -> List[List[Point]]:
        def at(ring: int, step: int) -> Point:
            polar: float = math.pi * ring / rings
            azimuth: float = 2 * math.pi * (step % segments) / segments
            return [
                x + radius * math.sin(polar) * math.cos(azimuth),
                y + radius * math.sin(polar) * math.sin(azimuth),
                z + radius * math.cos(polar),
            ]

        triangles: List[List[Point]] = []
        for ring in range(rings):
            for step in range(segments):
                if ring > 0:
                    triangles.append([at(ring, step), at(ring + 1, step), at(ring, step + 1)])
                if ring < rings - 1:
                    triangles.append([at(ring, step + 1), at(ring + 1, step), at(ring + 1, step + 1)])
        return triangles

    @classmethod
    def _sphere(cls, a: "AnnotationShape._Arguments") -> List[str]:
        triangles = cls._sphere_triangles(
            a.number("x"), a.number("y"), a.number("z"), a.size("radius"), a.count("rings", 8, 2), a.count("segments", 16, 3)
        )
        return [WellKnownText.write("TIN", True, [[[*triangle, triangle[0]]] for triangle in triangles])]

    @classmethod
    def _lollipop(cls, a: "AnnotationShape._Arguments") -> List[str]:
        x, y, z, height, radius = a.number("x"), a.number("y"), a.number("z"), a.size("height"), a.size("radius")
        if height <= 2 * radius:
            raise ValueError(f"height of the shape lollipop is above twice its radius ({2 * radius:g}), not {height:g}")

        stick: float = height - 2 * radius
        return [
            cls._solid(
                [*cls._cylinder_faces(x, y, z, radius / 5, stick, 12), *cls._sphere_triangles(x, y, z + height - radius, radius, 8, 16)]
            )
        ]
