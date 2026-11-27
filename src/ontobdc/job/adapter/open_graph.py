from pathlib import Path
from typing import BinaryIO, ClassVar, Dict, Tuple
from urllib.error import URLError
from urllib.parse import ParseResult, urlparse
from urllib.request import Request, urlopen

from rdflib import Graph
from rdflib.util import guess_format


class OpenGraph:
    """
    Reads an RDF graph from a public http or https address, or from a local filesystem path.

    A graph that cannot be opened, is not RDF, or holds no triple is an error.
    """

    SCHEMES: ClassVar[Tuple[str, ...]] = ("http", "https")
    TIMEOUT_SECONDS: ClassVar[int] = 30
    MAX_BYTES: ClassVar[int] = 32 * 1024 * 1024
    FORMATS: ClassVar[Dict[str, str]] = {
        "text/turtle": "turtle",
        "application/x-turtle": "turtle",
        "application/rdf+xml": "xml",
        "application/ld+json": "json-ld",
        "application/n-triples": "nt",
        "application/n-quads": "nquads",
        "text/n3": "n3",
    }
    # What a server answers for a file it does not know the type of: the format is then the one the name says.
    GENERIC_TYPES: ClassVar[Tuple[str, ...]] = ("text/plain", "application/octet-stream", "binary/octet-stream")
    ACCEPT: ClassVar[str] = ", ".join(FORMATS)

    @classmethod
    def load(cls, url: str) -> Graph:
        """
        The graph at an http or https address, or at a local filesystem path.

        Raises:
            ValueError: the source is unsupported, the graph cannot be opened, it is not RDF in a format
                OntoBDC knows, or it holds no triple.
        """
        parsed: ParseResult = urlparse(url)
        if parsed.scheme in cls.SCHEMES:
            if not parsed.netloc:
                raise ValueError(f"{url} is not an http or https address.")
            return cls._load_url(url, parsed)
        if parsed.scheme:
            raise ValueError(f"{url} is not an http or https address or local filesystem path.")

        return cls._load_path(url)

    @classmethod
    def _load_url(cls, url: str, parsed: ParseResult) -> Graph:
        try:
            with urlopen(Request(url, headers={"Accept": cls.ACCEPT}), timeout=cls.TIMEOUT_SECONDS) as response:
                content_type: str = response.headers.get_content_type()
                body: bytes = response.read(cls.MAX_BYTES + 1)
        except (URLError, OSError) as error:
            raise ValueError(f"{url} is not an open graph: {error}") from error
        if len(body) > cls.MAX_BYTES:
            raise ValueError(f"{url} is not an open graph: it is larger than {cls.MAX_BYTES} bytes.")

        rdf_format: str | None = cls.FORMATS.get(content_type)
        if rdf_format is None and content_type in cls.GENERIC_TYPES:
            rdf_format = guess_format(parsed.path)
        if rdf_format is None:
            hint: str = (
                " The page of a file on GitHub is HTML: use the address of its raw content."
                if parsed.netloc == "github.com" and "/blob/" in parsed.path
                else ""
            )
            raise ValueError(f"{url} is not an open graph: it answers {content_type}, which is not RDF.{hint}")

        return cls._parse_graph(url, body, rdf_format)

    @classmethod
    def _load_path(cls, source: str) -> Graph:
        path: Path = Path(source).expanduser()
        try:
            path = path.resolve(strict=True)
            if not path.is_file():
                raise ValueError(f"{source} is not an open graph: it is not a file.")
            graph_file: BinaryIO
            with path.open("rb") as graph_file:
                body: bytes = graph_file.read(cls.MAX_BYTES + 1)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"{source} is not an open graph: {error}") from error
        if len(body) > cls.MAX_BYTES:
            raise ValueError(f"{source} is not an open graph: it is larger than {cls.MAX_BYTES} bytes.")

        rdf_format: str | None = guess_format(str(path))
        if rdf_format is None:
            raise ValueError(f"{source} is not an open graph: its file extension does not identify an RDF format.")

        return cls._parse_graph(source, body, rdf_format, path.as_uri())

    @classmethod
    def _parse_graph(
        cls,
        source: str,
        body: bytes,
        rdf_format: str,
        public_id: str | None = None,
    ) -> Graph:
        graph: Graph = Graph()
        try:
            graph.parse(data=body, format=rdf_format, publicID=public_id)
        except Exception as error:
            raise ValueError(f"{source} is not an open graph: it is not valid {rdf_format}: {error}") from error
        if len(graph) == 0:
            raise ValueError(f"{source} is not an open graph: it holds no triples.")

        return graph
