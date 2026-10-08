import hashlib
from pathlib import Path
from typing import List
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from ontobdc.shared.domain.vocabulary import ICDD_CONTAINER as CT, ICDD_LINKSET as LS, OBDC
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class EntityLinkset:
    """
    The linkset that ties the data source of an entity to the documents the
    entities were made on.

    The data source is an internal document of the container, and a directed
    link goes from it to each source document. The source documents are
    named by their IRI in the container graph; the linkset never states
    where their file is. It is written to ``payload/linkset/<name>.ttl`` of
    the dataset, named after the data source file, so writing it again for
    the same data source replaces it.
    """

    LINKSET_DIRECTORY: Path = Path("payload") / "linkset"
    SUFFIX: str = ".ttl"
    FORMAT: str = "turtle"

    def __init__(self, dataset_path: Path, data_source_path: Path) -> None:
        self._dataset_path: Path = dataset_path.expanduser().resolve()
        self._data_source_path: Path = data_source_path.expanduser().resolve()

    @property
    def path(self) -> Path:
        return (
            self._dataset_path
            / self.LINKSET_DIRECTORY
            / f"{self._data_source_path.stem}{self.SUFFIX}"
        )

    @property
    def data_source_document(self) -> URIRef:
        relative_path: str = quote(
            self._data_source_path.relative_to(self._dataset_path).as_posix(),
            safe="/",
        )
        return URIRef(f"{self._dataset_iri()}/{relative_path}")

    def write(self, source_documents: List[str]) -> None:
        graph: Graph = Graph()
        graph.bind("ct", CT)
        graph.bind("ls", LS)

        data_source: URIRef = self.data_source_document
        data_source_element: URIRef = URIRef(f"{data_source}/link-element")
        graph.add((data_source, RDF.type, CT.InternalDocument))
        graph.add(
            (
                data_source,
                CT.filename,
                Literal(self._data_source_path.name, datatype=XSD.string),
            )
        )
        graph.add((data_source_element, RDF.type, LS.LinkElement))
        graph.add((data_source_element, LS.hasDocument, data_source))

        source_document: str
        for source_document in sorted(set(source_documents)):
            source: URIRef = URIRef(source_document)
            source_element: URIRef = URIRef(f"{source_document}/link-element")
            link: URIRef = URIRef(
                f"{data_source}/link/"
                f"{hashlib.sha256(source_document.encode('utf-8')).hexdigest()[:16]}"
            )
            graph.add((source_element, RDF.type, LS.LinkElement))
            graph.add((source_element, LS.hasDocument, source))
            graph.add((link, RDF.type, LS.DirectedBinaryLink))
            graph.add((link, LS.hasFromLinkElement, data_source_element))
            graph.add((link, LS.hasToLinkElement, source_element))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(graph.serialize(format=self.FORMAT, encoding="utf-8"))

    def links(self) -> List[str]:
        """
        The source documents the written linkset links the data source to.
        """
        if not self.path.is_file():
            return []

        graph: Graph = Graph()
        graph.parse(str(self.path), format=self.FORMAT)
        data_source_element: URIRef = URIRef(f"{self.data_source_document}/link-element")
        documents: List[str] = []
        link: URIRef
        for link in graph.subjects(LS.hasFromLinkElement, data_source_element):
            target: URIRef
            for target in graph.objects(link, LS.hasToLinkElement):
                document: URIRef
                for document in graph.objects(target, LS.hasDocument):
                    documents.append(str(document))

        return sorted(set(documents))

    def _dataset_iri(self) -> str:
        graph: Graph = Graph()
        graph.parse(
            str(StorageBootstrap.get_dataset_storage_file_path(self._dataset_path)),
            format="turtle",
        )
        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, OBDC.EntityDataset)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError(
                f"The metadata of the dataset at {self._dataset_path} declares "
                f"{len(subjects)} datasets, expected exactly one."
            )

        return str(subjects[0])
