from pathlib import Path
from typing import Any, Dict, List, Type

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, XSD

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.attachment_error import ContainerAttachError


_ontology_adapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
CT = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


def load_graph(
    path: Path,
    error_type: Type[ContainerAttachError],
) -> Graph:
    graph = Graph()
    try:
        graph.parse(str(path), format="turtle")
    except Exception as error:
        raise error_type(f"Could not read Turtle graph: {path}") from error
    return graph


def single_subject(
    graph: Graph,
    predicate: URIRef,
    object_value: URIRef,
    error_type: Type[ContainerAttachError],
    label: str,
) -> URIRef:
    subjects = [
        subject
        for subject in graph.subjects(predicate, object_value)
        if isinstance(subject, URIRef)
    ]
    if len(subjects) != 1:
        raise error_type(
            f"Expected exactly one {label} subject, found {len(subjects)}."
        )
    return subjects[0]


def required_object(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    error_type: Type[ContainerAttachError],
    label: str,
) -> Any:
    values = list(graph.objects(subject, predicate))
    if len(values) != 1 or not str(values[0]).strip():
        raise error_type(f"Expected exactly one {label}.")
    return values[0]


def required_literal(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    error_type: Type[ContainerAttachError],
    label: str,
) -> str:
    value = required_object(
        graph,
        subject,
        predicate,
        error_type,
        label,
    )
    if not isinstance(value, Literal):
        raise error_type(f"Expected {label} to be a literal.")
    return str(value).strip()


def required_uri(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    error_type: Type[ContainerAttachError],
    label: str,
) -> str:
    value = required_object(
        graph,
        subject,
        predicate,
        error_type,
        label,
    )
    if not isinstance(value, URIRef):
        raise error_type(f"Expected {label} to be a URI.")
    return str(value).strip()


def rewrite_graph(
    graph: Graph,
    mapping: Dict[URIRef, URIRef],
) -> Graph:
    rewritten = Graph()
    for prefix, namespace in graph.namespaces():
        rewritten.bind(prefix, namespace)
    rewritten.bind("dcterms", DCTERMS)
    rewritten.bind("ct", CT)
    rewritten.bind("prov", PROV)
    rewritten.bind("xsd", XSD)
    rewritten.bind("obdc", OBDC)
    rewritten.bind("owl", OWL)
    for subject, predicate, object_value in graph:
        rewritten.add(
            (
                mapping.get(subject, subject),
                predicate,
                mapping.get(object_value, object_value),
            )
        )
    return rewritten


def set_single(
    graph: Graph,
    subject: URIRef,
    predicate: URIRef,
    object_value: Any,
) -> None:
    graph.remove((subject, predicate, None))
    graph.add((subject, predicate, object_value))


def remove_subject(graph: Graph, subject: URIRef) -> None:
    for predicate, object_value in list(graph.predicate_objects(subject)):
        graph.remove((subject, predicate, object_value))
    for source, predicate in list(graph.subject_predicates(subject)):
        graph.remove((source, predicate, subject))


def matching_container_subjects(
    graph: Graph,
    *,
    source_subject: URIRef,
    target_subject: URIRef,
    source_id: str,
    target_id: str,
    source_location: str,
    target_location: str,
) -> List[URIRef]:
    subjects: List[URIRef] = []
    for subject in graph.subjects(RDF.type, OBDC.DataContainer):
        if not isinstance(subject, URIRef) or subject in subjects:
            continue
        identifiers = {
            str(value).strip()
            for value in graph.objects(subject, DCTERMS.identifier)
        }
        locations = {
            str(value).strip()
            for value in graph.objects(subject, PROV.atLocation)
        }
        if (
            subject in {source_subject, target_subject}
            or identifiers.intersection({source_id, target_id})
            or locations.intersection({source_location, target_location})
        ):
            subjects.append(subject)
    return subjects
