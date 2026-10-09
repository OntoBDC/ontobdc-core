from pathlib import Path
from typing import ClassVar, List

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary
from ontobdc.shared.domain.model.facade import FacadeField, ResourceFacade


class ResourceFacadeReader:
    """
    Reads the public projection an ontology declares for a resource.

    The facade is the contract between what a user names and what the graph
    stores: each field carries the identifier a person types, the label an
    input shows, and the property the value is written to. Reading it here
    keeps that mapping in the ontology, where it is declared, instead of
    duplicating it as a table in code.
    """

    FACADE: ClassVar[Namespace] = Namespace(
        "http://ontobdc.org/ontology/domain/facade.ttl#"
    )
    SCHEMA: ClassVar[Namespace] = Namespace("https://schema.org/")

    def __init__(self, facade_path: Path) -> None:
        if not facade_path.is_file():
            raise FileNotFoundError(f"Resource facade not found: {facade_path}")

        self._facade_path: Path = facade_path
        self._graph: Graph = Graph()
        self._graph.parse(str(facade_path), format="turtle")

    def read(self) -> ResourceFacade:
        """
        Return the single resource facade the ontology file declares.
        """
        subjects: List[URIRef] = [
            subject
            for subject in self._graph.subjects(RDF.type, self.FACADE.ResourceFacade)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise ValueError(
                f"Resource facade file must declare exactly one facade: "
                f"{self._facade_path}"
            )

        subject: URIRef = subjects[0]
        fields: List[FacadeField] = [
            self._read_field(field_subject)
            for field_subject in self._graph.objects(
                subject,
                self.FACADE.hasFacadeField,
            )
            if isinstance(field_subject, URIRef)
        ]

        return ResourceFacade(
            identifier=self._text(subject, self.SCHEMA.identifier),
            name=self._text(subject, self.SCHEMA.name),
            description=self._text(subject, self.SCHEMA.description),
            fields=sorted(fields, key=lambda declared: declared.order),
        )

    def _read_field(self, subject: URIRef) -> FacadeField:
        """
        Return the field the given individual declares.
        """
        return FacadeField(
            identifier=self._text(subject, self.SCHEMA.identifier),
            name=self._text(subject, self.SCHEMA.name),
            description=self._text(subject, self.SCHEMA.description),
            datatype=self._iri(subject, self.FACADE.fieldDatatype),
            order=self._integer(subject, self.FACADE.fieldOrder),
            maps_to_property=self._iri(subject, self.FACADE.mapsToProperty),
            required=self._flag(subject, self.FACADE.isRequired),
            editable=self._flag(subject, self.FACADE.isEditable),
        )

    def _value(self, subject: URIRef, predicate: URIRef) -> object:
        """
        Return the single object declared for the subject and predicate.
        """
        value: object = self._graph.value(subject, predicate)
        if value is None:
            raise ValueError(
                f"Resource facade declares no {predicate} for {subject} "
                f"in {self._facade_path}"
            )

        return value

    def _text(self, subject: URIRef, predicate: URIRef) -> str:
        """
        Return a declared literal as text.
        """
        return str(self._value(subject, predicate))

    def _iri(self, subject: URIRef, predicate: URIRef) -> str:
        """
        Return a declared IRI as text.
        """
        value: object = self._value(subject, predicate)
        if not isinstance(value, URIRef):
            raise ValueError(
                f"Resource facade declares {predicate} of {subject} as a "
                f"literal, expected an IRI, in {self._facade_path}"
            )

        return str(value)

    def _integer(self, subject: URIRef, predicate: URIRef) -> int:
        """
        Return a declared literal as an integer.
        """
        value: object = self._value(subject, predicate)
        if not isinstance(value, Literal):
            raise ValueError(
                f"Resource facade declares {predicate} of {subject} as an "
                f"IRI, expected a literal, in {self._facade_path}"
            )

        return int(value)

    def _flag(self, subject: URIRef, predicate: URIRef) -> bool:
        """
        Return a declared literal as a boolean.
        """
        value: object = self._value(subject, predicate)
        if not isinstance(value, Literal):
            raise ValueError(
                f"Resource facade declares {predicate} of {subject} as an "
                f"IRI, expected a literal, in {self._facade_path}"
            )

        return bool(value.toPython())


class DataContainerFacade:
    """
    The public projection of the storage container.
    """

    # brasidatacenter commit 6d9e604 moved this file to
    # tbox/facade/data_container.ttl; the ontology's own owl:Ontology IRI
    # is unchanged, but BrasidataCenterOntologyLibrary resolves an IRI to
    # a file 1:1, so only the physical path here needs to follow.
    ONTOLOGY_IRI: ClassVar[str] = (
        "http://datacenter.app.br/ontology/tool/ontobdc/tbox/facade/data_container.ttl"
    )

    @classmethod
    def read(cls) -> ResourceFacade:
        """
        Return the container facade the installed ontology declares.

        Raises:
            FileNotFoundError: the installed ontologies have none at
                ``ONTOLOGY_IRI``.
        """
        return ResourceFacadeReader(
            BrasidataCenterOntologyLibrary().path(cls.ONTOLOGY_IRI)
        ).read()
