from typing import Any, ClassVar, Dict, List, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD, Namespace

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary
from ontobdc.container.domain.exception.entity import EntityFacadeNotFoundError
from ontobdc.container.domain.model.entity_facade import (
    EntityFacade,
    EntityFacadeField,
)


class EntityFacadeLocator:
    """
    Find the facade the ontologies publish for an entity type.

    Each facade declares which entity class it is the facade of, so the
    entity is all it takes to find one.
    """

    FACADE: ClassVar[Namespace] = Namespace(
        "http://datacenter.app.br/ontology/tool/ontobdc/facade/ns.ttl#"
    )
    SCHEMA: ClassVar[Namespace] = Namespace("https://schema.org/")

    @classmethod
    def of(cls, entity_iri: str) -> EntityFacade:
        """
        Raises:
            EntityFacadeNotFoundError: no ontology publishes a facade of
                ``entity_iri``.
            ValueError: the facade lacks something a field needs.
        """
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        iri: str
        for iri in library.iris():
            graph: Graph = library.graph(iri)
            subject: Optional[URIRef] = cls._facade_of(graph, entity_iri)
            if subject is not None:
                return cls._read(graph, subject, entity_iri)

        raise EntityFacadeNotFoundError(
            f"No ontology publishes a facade of the entity <{entity_iri}>."
        )

    @classmethod
    def _facade_of(cls, graph: Graph, entity_iri: str) -> Optional[URIRef]:
        subject: Any
        for subject in graph.subjects(RDF.type, cls.FACADE.DataEntityFacade):
            if (subject, cls.FACADE.isFacadeOf, URIRef(entity_iri)) in graph:
                return subject if isinstance(subject, URIRef) else None

        return None

    @classmethod
    def _read(cls, graph: Graph, subject: URIRef, entity_iri: str) -> EntityFacade:
        fields: List[EntityFacadeField] = [
            cls._read_field(graph, field_subject)
            for field_subject in graph.objects(subject, cls.FACADE.hasFacadeField)
            if isinstance(field_subject, URIRef)
        ]
        return EntityFacade(
            identifier=cls._required_text(graph, subject, cls.SCHEMA.identifier),
            name=cls._label(graph, subject),
            entity_iri=entity_iri,
            creatable=cls._declared_flag(graph, subject, cls.FACADE.isCreatable),
            fields=sorted(fields, key=lambda declared: declared.order),
        )

    @classmethod
    def _read_field(cls, graph: Graph, subject: URIRef) -> EntityFacadeField:
        return EntityFacadeField(
            identifier=cls._required_text(graph, subject, cls.SCHEMA.identifier),
            datatype=cls._required_text(graph, subject, cls.FACADE.fieldDatatype),
            order=int(cls._required_text(graph, subject, cls.FACADE.fieldOrder)),
            required=cls._flag(graph, subject, cls.FACADE.isRequired),
            multivalued=cls._flag(graph, subject, cls.FACADE.isMultivalued),
            maps_to_resource=cls._required_text(
                graph, subject, cls.FACADE.mapsToResource
            ),
            editable=cls._declared_flag(graph, subject, cls.FACADE.isEditable),
            default=cls._generator(graph, subject),
            options=cls._options(graph, subject),
            labels=cls._labels(graph, subject),
        )

    @classmethod
    def _labels(cls, graph: Graph, subject: URIRef) -> Dict[str, str]:
        """
        The names the facade gives the field, by lower-case language tag.
        """
        return {
            str(label.language).lower(): str(label)
            for label in graph.objects(subject, cls.SCHEMA.name)
            if isinstance(label, Literal) and label.language
        }

    @staticmethod
    def _required_text(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
        value: Any = graph.value(subject, predicate)
        if value is None or not str(value).strip():
            raise ValueError(f"The facade declares no {predicate} for {subject}.")

        return str(value).strip()

    @classmethod
    def _options(cls, graph: Graph, subject: URIRef) -> List[str]:
        """
        The identifiers (``dcterms:identifier``) of the direct subclasses of the
        class the facade says the field takes its values from; none when it
        does not say so.
        """
        parent: Any = graph.value(subject, cls.FACADE.hasValuesFromSubclassesOf)
        if not isinstance(parent, URIRef):
            return []

        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        identifiers: set[str] = set()
        iri: str
        for iri in library.iris():
            ontology: Graph = library.graph(iri)
            child: Any
            for child in ontology.subjects(RDFS.subClassOf, parent):
                identifier: Any = ontology.value(child, DCTERMS.identifier)
                if isinstance(identifier, Literal):
                    identifiers.add(str(identifier))

        return sorted(identifiers)

    @classmethod
    def _generator(cls, graph: Graph, subject: URIRef) -> Optional[str]:
        """The IRI of the value generator the facade gives the field as its default, if any."""
        generator: Any = graph.value(subject, cls.FACADE.hasDefault)
        return str(generator) if isinstance(generator, URIRef) else None

    @classmethod
    def _declared_flag(cls, graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
        """A flag the facade may leave out: what it does not say is false."""
        if graph.value(subject, predicate) is None:
            return False

        return cls._flag(graph, subject, predicate)

    @staticmethod
    def _flag(graph: Graph, subject: URIRef, predicate: URIRef) -> bool:
        value: Any = graph.value(subject, predicate)
        if not isinstance(value, Literal) or value.datatype != XSD.boolean:
            raise ValueError(f"The facade declares no boolean {predicate} for {subject}.")

        return bool(value.toPython())

    @classmethod
    def _label(cls, graph: Graph, subject: URIRef) -> str:
        labels: List[Any] = list(graph.objects(subject, cls.SCHEMA.name))
        label: Any
        for label in labels:
            if isinstance(label, Literal) and label.language == "en":
                return str(label)

        if not labels:
            raise ValueError(f"The facade declares no name for {subject}.")

        return str(labels[0])
