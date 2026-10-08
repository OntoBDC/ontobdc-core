from pathlib import Path
from typing import ClassVar, List, Optional
from urllib.parse import quote, unquote

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.bootstrap import StorageBootstrap


class ContainerDocumentIri:
    """
    The IRI of a file as a document of its container.

    A document is named by the container that holds it and by its path in
    the container, so the same file always gets the same IRI and the IRI
    never states where the container is:

        urn:ontobdc:storage/container/<container id>/payload/document/<path>

    Both the identifier of the container and the path are percent-encoded.
    """

    SCHEME: ClassVar[str] = "urn:ontobdc:storage/container/"
    DOCUMENT_SEGMENTS: ClassVar[str] = "/payload/document/"

    @classmethod
    def of(cls, container_path: Path, file_path: Path) -> URIRef:
        """
        Raises:
            ValueError: the file is not inside the container, or the
                container carries no identifier.
        """
        container: Path = container_path.expanduser().resolve()
        try:
            relative_path: str = file_path.expanduser().resolve().relative_to(
                container
            ).as_posix()
        except ValueError as error:
            raise ValueError(f"{file_path} is not inside the container {container}.") from error

        return URIRef(
            f"{cls.SCHEME}{quote(cls.container_id(container), safe='')}"
            f"{cls.DOCUMENT_SEGMENTS}{quote(relative_path, safe='/')}"
        )

    @classmethod
    def path_of(cls, container_path: Path, iri: str) -> Optional[str]:
        """
        The path, in the container, of the file a document IRI names: the
        inverse of ``of``. None for an IRI that is not a document of this
        container.
        """
        prefix: str = (
            f"{cls.SCHEME}{quote(cls.container_id(container_path.expanduser().resolve()), safe='')}"
            f"{cls.DOCUMENT_SEGMENTS}"
        )
        if not iri.startswith(prefix) or len(iri) == len(prefix):
            return None

        return unquote(iri[len(prefix):])

    @classmethod
    def container_of(cls, file_path: Path) -> Path:
        """
        The nearest container above the file: the first directory that
        carries a container metadata file.

        Raises:
            LookupError: no directory above the file is a container.
        """
        directory: Path
        for directory in file_path.expanduser().resolve().parents:
            if StorageBootstrap.get_container_storage_file_path(directory).is_file():
                return directory

        raise LookupError(f"{file_path} is not inside any container.")

    @classmethod
    def container_id(cls, container_path: Path) -> str:
        graph: Graph = Graph()
        graph.parse(
            str(StorageBootstrap.get_container_storage_file_path(container_path)),
            format="turtle",
        )
        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(RDF.type, OBDC.DataContainer)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError(
                f"The container at {container_path} declares {len(subjects)} "
                f"data containers, expected exactly one."
            )

        identifiers: List[str] = [
            str(identifier).strip()
            for identifier in graph.objects(subjects[0], DCTERMS.identifier)
            if str(identifier).strip()
        ]
        return identifiers[0] if len(identifiers) == 1 else str(subjects[0])
