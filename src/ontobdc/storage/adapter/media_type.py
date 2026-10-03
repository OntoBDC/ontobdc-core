import mimetypes
from functools import lru_cache
from pathlib import PurePath
from typing import ClassVar, Dict, Optional, Tuple

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary


class MediaTypeResolver:
    """
    The media type of a file, from its extension.

    The media types of the domain's own formats (IFC, DXF, ...) are declared
    in the AECO ontology as ``aeco:FileEncoding`` individuals, each with the
    ``aeco:fileExtension`` that identifies it and the ``aeco:mediaType`` its
    files are recorded with. Any other extension is looked up in the table
    built into Python, never in the operating system's ``mime.types`` files,
    so the same file is recorded with the same media type on every machine.
    An extension neither knows has no media type.
    """

    CATALOG_IRI: ClassVar[str] = "http://datacenter.app.br/ontology/domain/aeco/catalog.ttl"
    #: The prefix the catalog binds to the AECO core schema.
    AECO_PREFIX: ClassVar[str] = "aeco"

    _BUILT_IN: ClassVar[mimetypes.MimeTypes] = mimetypes.MimeTypes()

    @classmethod
    def of(cls, file_name: str) -> Optional[str]:
        """
        The media type of the file named ``file_name``.
        """
        return cls.guess(file_name)[0]

    @classmethod
    def guess(cls, file_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        The media type of the file named ``file_name`` and the encoding
        (``gzip``, ...) it is compressed with, if any.
        """
        built_in_type: Optional[str]
        encoding: Optional[str]
        built_in_type, encoding = cls._BUILT_IN.guess_type(file_name)

        name: PurePath = PurePath(file_name)
        if encoding is not None:
            name = PurePath(name.stem)
        extension: str = name.suffix.lstrip(".").lower()

        declared_type: Optional[str] = cls._declared_media_types().get(extension)
        if declared_type is not None:
            return declared_type, encoding
        return built_in_type, encoding

    @classmethod
    @lru_cache(maxsize=1)
    def _declared_media_types(cls) -> Dict[str, str]:
        """
        Every file extension the AECO ontology declares, mapped to its media
        type. Read once per process.
        """
        graph: Graph = BrasidataCenterOntologyLibrary().graph_with_imports(cls.CATALOG_IRI)
        aeco: Namespace = BrasidataCenterOntologyLibrary.bound_namespace(graph, cls.AECO_PREFIX)

        media_types: Dict[str, str] = {}
        for file_encoding in graph.subjects(RDF.type, aeco.FileEncoding):
            media_type: object = graph.value(file_encoding, aeco.mediaType)
            if media_type is None:
                continue
            for extension in graph.objects(file_encoding, aeco.fileExtension):
                media_types[str(extension).strip().lstrip(".").lower()] = str(media_type)

        return media_types
