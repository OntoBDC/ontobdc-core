from typing import Any, ClassVar, Dict, List
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDFS, SKOS

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.plugin.capability.transformation.ontology_terms_matched import (
    _LabelNormalizer,
)
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.etl import (
    AnnotationCreationFromPointEtlEvent,
)
from ontobdc.annotate.plugin.machine.annotation_creation_from_point.state import (
    AnnotationCreationFromPointProcessState,
)


class AnnotationTypeIdentifiedCapability(TransactionCapability):
    """
    Identify the type of the annotation to create.

    The type is named by a parameter of the context, as its IRI or by a
    label or identifier any language gives it. It is resolved against the
    annotation types the Brasidatacenter ontology declares, and the graph
    that describes the identified type is persisted as the ETL event
    ``__annotation_type_identified__.jsonld``.
    """

    STATE_NAME: ClassVar[str] = "annotation_type_identified"
    ANNOTATION_TYPE_KEY: ClassVar[str] = "annotation_type"
    EVENT_SUFFIX: ClassVar[str] = ".jsonld"

    ONTOLOGY_IRI: ClassVar[str] = (
        "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl"
    )
    ANNOTATION_CLASS: ClassVar[URIRef] = URIRef(ONTOLOGY_IRI + "#Annotation")
    NAME_PREDICATES: ClassVar[List[URIRef]] = [
        SKOS.prefLabel,
        SKOS.altLabel,
        RDFS.label,
        DCTERMS.identifier,
    ]

    ANNOTATION_TYPE_IRI_KEY: ClassVar[str] = "annotation_type_iri"
    EVENT_PATH_KEY: ClassVar[str] = "event_path"

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.annotate.plugin.capability.transformation.target."
            "annotation_type_identified"
        ),
        version="1.0.0",
        name="Annotation Type Identified",
        description=(
            "Resolve the named annotation type to its IRI in the "
            "Brasidatacenter annotation types and persist the graph of the "
            "type as an ETL state event."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["annotation", "type", "ontology", "etl"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "properties": {
                ANNOTATION_TYPE_KEY: {
                    "type": "string",
                    "required": True,
                },
            },
        },
        output_schema={
            "properties": {
                ANNOTATION_TYPE_IRI_KEY: {"type": "string"},
                EVENT_PATH_KEY: {"type": "string"},
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Tipo da anotação identificado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def is_satisfied(self, context: CliContextPort) -> bool:
        """
        Whether the persisted event is the graph of the type now named.
        """
        if RequiredParameter.optional(context, self.ANNOTATION_TYPE_KEY) is None:
            return False

        event_path: Path = self.event_path(
            AnnotationCreationFromPointEtlEvent.container_of(context)
        )
        if not event_path.is_file():
            return False

        type_graph: Graph = self._type_graph(self._ontology(), self._identify(context))
        event_graph: Graph = Graph()
        event_graph.parse(str(event_path), format="json-ld")
        return set(event_graph) == set(type_graph)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        annotation_type: URIRef = self._identify(context)
        event_path: Path = self._write_event(
            AnnotationCreationFromPointEtlEvent.container_of(context),
            self._type_graph(self._ontology(), annotation_type),
        )
        return {
            self.ANNOTATION_TYPE_IRI_KEY: str(annotation_type),
            self.EVENT_PATH_KEY: str(event_path),
        }

    @classmethod
    def annotation_type_iri(cls, context: CliContextPort) -> URIRef:
        """
        The IRI of the annotation type the context names.

        Raises:
            LookupError: no annotation type goes by that name.
            ValueError: more than one does.
        """
        return cls._identify(context)

    @classmethod
    def identifier_of(cls, annotation_type: URIRef) -> str:
        """
        The identifier the ontology gives the annotation type (``issue``).

        Raises:
            LookupError: the ontology gives the type none.
        """
        identifier: Any = cls._ontology().value(annotation_type, DCTERMS.identifier)
        if identifier is None or not str(identifier).strip():
            raise LookupError(f"The annotation type <{annotation_type}> has no identifier.")

        return str(identifier).strip()

    @classmethod
    def event_path(cls, container_path: Path) -> Path:
        return AnnotationCreationFromPointEtlEvent.path(
            container_path,
            AnnotationCreationFromPointProcessState.ANNOTATION_TYPE_IDENTIFIED,
        ).with_suffix(cls.EVENT_SUFFIX)

    @classmethod
    def _ontology(cls) -> Graph:
        return BrasidataCenterOntologyLibrary().graph(cls.ONTOLOGY_IRI)

    @classmethod
    def _identify(cls, context: CliContextPort) -> URIRef:
        """
        The annotation type the context names.

        Raises:
            LookupError: no annotation type goes by that name.
            ValueError: more than one does.
        """
        requested: str = RequiredParameter.of(context, cls.ANNOTATION_TYPE_KEY)
        ontology: Graph = cls._ontology()
        types: List[URIRef] = sorted(
            {
                subject
                for subject in ontology.subjects(RDFS.subClassOf, cls.ANNOTATION_CLASS)
                if isinstance(subject, URIRef)
            }
        )

        wanted: str = _LabelNormalizer.normalize(requested)
        matches: List[URIRef] = [
            annotation_type
            for annotation_type in types
            if str(annotation_type) == requested
            or wanted
            in {
                _LabelNormalizer.normalize(str(name))
                for predicate in cls.NAME_PREDICATES
                for name in ontology.objects(annotation_type, predicate)
                if isinstance(name, Literal)
            }
        ]
        if not matches:
            raise LookupError(
                f"No annotation type is named '{requested}'. The annotation "
                f"types are: {', '.join(str(annotation_type) for annotation_type in types)}."
            )
        if len(matches) > 1:
            raise ValueError(
                f"'{requested}' names more than one annotation type: "
                f"{', '.join(str(annotation_type) for annotation_type in matches)}."
            )
        return matches[0]

    @staticmethod
    def _type_graph(ontology: Graph, annotation_type: URIRef) -> Graph:
        """
        What the ontology says about the type: its concise bounded description.
        """
        return ontology.cbd(annotation_type)

    @classmethod
    def _write_event(cls, container_path: Path, type_graph: Graph) -> Path:
        event_path: Path = cls.event_path(container_path)
        AnnotationCreationFromPointEtlEvent.write_text(
            event_path,
            type_graph.serialize(format="json-ld", indent=2),
        )
        return event_path
