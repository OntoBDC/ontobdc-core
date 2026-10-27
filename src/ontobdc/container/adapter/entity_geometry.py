import re
from pathlib import Path
from typing import ClassVar, List, NamedTuple, Optional, Tuple

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD


class EntityGeometry(NamedTuple):
    """
    One geometry of an entity: its identifier, which stays when the others come and go, its well-known text and how it is drawn, which the text cannot say: the colour of its
    border, the width of its border and the colour of its fill, and the shape it was made as (a circle, say, which the
    text says only as a polygon). Each one is absent when it was never chosen.
    """

    id: str
    wkt: str
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    fill: Optional[str] = None
    shape: Optional[str] = None


class EntityGeometries:
    """
    The geometries of an entity, as the GeoSPARQL ontology says them: the entity has geometries, and each one is a
    node with its well-known text, its number of dimensions and its place in the list.

    They are kept as Turtle in the dataset of the entity, in ``payload/triple/geometry_<global id of the entity>.ttl``,
    beside the row of the entity and not in it: a geometry may be a mesh of thousands of points, which a cell of a
    spreadsheet should not carry and the listing of the entities should not read. An entity with no geometry has no
    file. A geometry is not an entity, whatever the files of ``payload/triple`` say: only what the dataset declares as
    its data entities is one.
    """

    GEO: ClassVar[Namespace] = Namespace("http://www.opengis.net/ont/geosparql#")
    SCHEMA: ClassVar[Namespace] = Namespace("http://schema.org/")
    STYLE: ClassVar[Namespace] = Namespace("urn:ontobdc:style:")
    DIRECTORY: ClassVar[Path] = Path("payload") / "triple"
    PREFIX: ClassVar[str] = "geometry_"
    SUFFIX: ClassVar[str] = ".ttl"
    FORMAT: ClassVar[str] = "turtle"
    HEADER: ClassVar["re.Pattern[str]"] = re.compile(r"^\s*([A-Za-z]+)(\s+Z)?\b")

    @classmethod
    def path(cls, dataset_path: Path, entity_id: str) -> Path:
        return dataset_path.expanduser().resolve() / cls.DIRECTORY / f"{cls.PREFIX}{entity_id}{cls.SUFFIX}"

    @staticmethod
    def entity(entity_id: str) -> URIRef:
        """The resource of the entity, as the one of its comments is."""
        return URIRef(f"urn:ontobdc:entity:{entity_id}")

    @staticmethod
    def geometry(entity_id: str, identifier: str) -> URIRef:
        return URIRef(f"urn:ontobdc:geometry:{entity_id}/{identifier}")

    @classmethod
    def describe(cls, wkt: str) -> Tuple[str, int]:
        """The kind of a geometry and its number of dimensions, from the beginning of its text: ``("POLYGON", 3)``."""
        header = cls.HEADER.match(wkt)
        if header is None:
            raise ValueError(f"not the well-known text of a geometry: {wkt!r}")

        return header.group(1).upper(), 3 if header.group(2) else 2

    @classmethod
    def read(cls, dataset_path: Path, entity_id: str) -> List[EntityGeometry]:
        """Each geometry of the entity, in the order they were written; none when it has none."""
        path: Path = cls.path(dataset_path, entity_id)
        if not path.is_file():
            return []

        graph: Graph = Graph()
        graph.parse(str(path), format=cls.FORMAT)
        found: List[Tuple[int, EntityGeometry]] = []
        node: URIRef
        for node in graph.objects(cls.entity(entity_id), cls.GEO.hasGeometry):
            wkt: object = graph.value(node, cls.GEO.asWKT)
            position: object = graph.value(node, cls.SCHEMA.position)
            if wkt is not None:
                stroke: object = graph.value(node, cls.STYLE.stroke)
                width: object = graph.value(node, cls.STYLE.strokeWidth)
                fill: object = graph.value(node, cls.STYLE.fill)
                shape: object = graph.value(node, cls.SCHEMA.name)
                found.append(
                    (
                        int(str(position)) if position is not None else 0,
                        EntityGeometry(
                            str(node).rsplit("/", 1)[-1],
                            str(wkt),
                            str(stroke) if stroke is not None else None,
                            float(str(width)) if width is not None else None,
                            str(fill) if fill is not None else None,
                            str(shape) if shape is not None else None,
                        ),
                    )
                )

        return [geometry for _, geometry in sorted(found, key=lambda item: item[0])]

    @classmethod
    def write(cls, dataset_path: Path, entity_id: str, geometries: List[EntityGeometry]) -> None:
        """Make these the geometries of the entity, in this order. With none, the file is removed."""
        path: Path = cls.path(dataset_path, entity_id)
        if not geometries:
            path.unlink(missing_ok=True)
            return

        graph: Graph = Graph()
        graph.bind("geo", cls.GEO)
        graph.bind("schema", cls.SCHEMA, override=True, replace=True)
        graph.bind("style", cls.STYLE)
        entity: URIRef = cls.entity(entity_id)
        position: int
        geometry: EntityGeometry
        for position, geometry in enumerate(geometries):
            wkt: str = geometry.wkt
            node: URIRef = cls.geometry(entity_id, geometry.id)
            graph.add((entity, cls.GEO.hasGeometry, node))
            graph.add((node, RDF.type, cls.GEO.Geometry))
            graph.add((node, cls.GEO.asWKT, Literal(wkt, datatype=cls.GEO.wktLiteral)))
            graph.add(
                (
                    node,
                    cls.GEO.coordinateDimension,
                    Literal(cls.describe(wkt)[1], datatype=XSD.integer),
                )
            )
            graph.add((node, cls.SCHEMA.position, Literal(position, datatype=XSD.integer)))
            if geometry.shape is not None:
                graph.add((node, cls.SCHEMA.name, Literal(geometry.shape)))
            if geometry.stroke is not None:
                graph.add((node, cls.STYLE.stroke, Literal(geometry.stroke)))
            if geometry.stroke_width is not None:
                graph.add((node, cls.STYLE.strokeWidth, Literal(geometry.stroke_width, datatype=XSD.decimal)))
            if geometry.fill is not None:
                graph.add((node, cls.STYLE.fill, Literal(geometry.fill)))

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(graph.serialize(format=cls.FORMAT), encoding="utf-8")

    @classmethod
    def delete(cls, dataset_path: Path, entity_id: str) -> None:
        """Forget the geometries of an entity that is gone."""
        cls.path(dataset_path, entity_id).unlink(missing_ok=True)
