from typing import Any, ClassVar, Dict, List

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDFS, SKOS

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary


class AnnotationTypes:
    """
    The annotation types the Brasidatacenter ontology declares.

    A type is a subclass of ``Annotation`` in the ontology, so a type added
    there is a type here, with no list in code to keep in step.
    """

    ONTOLOGY_IRI: ClassVar[str] = (
        "http://datacenter.app.br/ontology/domain/annotation/taxonomy/type.ttl"
    )
    ANNOTATION_CLASS: ClassVar[URIRef] = URIRef(ONTOLOGY_IRI + "#Annotation")

    @classmethod
    def all(cls) -> List[Dict[str, Any]]:
        """
        Every annotation type, ordered by identifier: its IRI, its
        identifier and its label by language (lower-case language tag).

        Raises:
            ValueError: a type has no identifier.
        """
        ontology: Graph = BrasidataCenterOntologyLibrary().graph(cls.ONTOLOGY_IRI)
        types: List[Dict[str, Any]] = []
        annotation_type: Any
        for annotation_type in ontology.subjects(RDFS.subClassOf, cls.ANNOTATION_CLASS):
            if not isinstance(annotation_type, URIRef):
                continue

            identifier: Any = ontology.value(annotation_type, DCTERMS.identifier)
            if identifier is None or not str(identifier).strip():
                raise ValueError(f"The annotation type <{annotation_type}> has no identifier.")

            types.append(
                {
                    "iri": str(annotation_type),
                    "identifier": str(identifier).strip(),
                    "labels": cls._labels(ontology, annotation_type),
                }
            )

        return sorted(types, key=lambda declared: declared["identifier"])

    @staticmethod
    def _labels(ontology: Graph, annotation_type: URIRef) -> Dict[str, str]:
        labels: Dict[str, str] = {}
        label: Any
        for label in ontology.objects(annotation_type, SKOS.prefLabel):
            if isinstance(label, Literal) and label.language:
                labels[label.language.lower()] = str(label)

        return labels
