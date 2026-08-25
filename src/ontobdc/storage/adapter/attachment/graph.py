from pathlib import Path
from typing import Any, Dict, List, Set, Type

from rdflib import Graph, Literal, Node, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, XSD, Namespace

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage.adapter.attachment.error import ContainerAttachError


_URI_PREFIXES: tuple = ("http://", "https://", "urn:", "file:", "ftp://")


def _to_rdflib_object(value: Any) -> Any:
    if isinstance(value, Node):
        return value
    if isinstance(value, str):
        stripped: str = value.strip()
        lower: str = stripped.lower()
        if lower.startswith(_URI_PREFIXES):
            return URIRef(stripped)
        return Literal(stripped)
    return value


class AttachmentGraphNamespaceBootstrap:
    """Initialize, cache, and expose the storage-level ontology namespaces.

    Mirrors the exact same initialization pattern used in
    :mod:`ontobdc.storage.adapter.bootstrap` and
    :mod:`ontobdc.storage.adapter.repository` — the ontology adapter is
    instantiated once (with the project-root-unset default) and kept on a
    class attribute so repeated module imports / reloads do not re-run the
    namespace lookup.
    """

    _ontology_adapter: "OntologyConfigAdapter | None" = None
    CT: Namespace
    OBDC: Namespace

    @classmethod
    def _adapter(cls) -> OntologyConfigAdapter:
        if cls._ontology_adapter is None:
            cls._ontology_adapter = OntologyConfigAdapter(
                config_adapter=UnsetProjectRootConfigDataAdapter(),
            )
        return cls._ontology_adapter

    @classmethod
    def initialize(cls) -> None:
        adapter: OntologyConfigAdapter = cls._adapter()
        cls.CT = adapter.get_ontology_namespace_by_prefix("ct")
        cls.OBDC = adapter.get_ontology_namespace_by_prefix("obdc")


AttachmentGraphNamespaceBootstrap.initialize()


class AttachmentGraphOperations:
    """Pure stateless helpers for reading, querying, and mutating RDF graphs.

    Every helper that used to live at module-level is exposed here as a
    classmethod. Nothing on this class carries per-instance state — the
    owning service (e.g. ``AttachmentMetadataService``) is responsible for
    supplying the concrete ``Graph``, ``URIRef``, and error-type values.
    """

    @classmethod
    def load_graph(
        cls,
        path: Path,
        error_type: Type[ContainerAttachError],
    ) -> Graph:
        graph: Graph = Graph()
        try:
            graph.parse(str(path), format="turtle")
        except Exception as error:
            raise error_type(f"Could not read Turtle graph: {path}") from error
        return graph

    @classmethod
    def single_subject(
        cls,
        graph: Graph,
        predicate: URIRef,
        object_value: URIRef,
        error_type: Type[ContainerAttachError],
        label: str,
    ) -> URIRef:
        subjects: List[URIRef] = [
            subject
            for subject in graph.subjects(predicate, object_value)
            if isinstance(subject, URIRef)
        ]
        if len(subjects) != 1:
            raise error_type(
                f"Expected exactly one {label} subject, found {len(subjects)}."
            )
        return subjects[0]

    @classmethod
    def required_object(
        cls,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        error_type: Type[ContainerAttachError],
        label: str,
    ) -> Any:
        raw_values: List[Any] = list(graph.objects(subject, predicate))
        normalized: List[Any] = []
        seen_values: Set[str] = set()
        value: Any
        for value in raw_values:
            normalized_text: str = str(value).strip()
            if not normalized_text:
                continue
            if normalized_text in seen_values:
                continue
            seen_values.add(normalized_text)
            normalized.append(value)
        if len(normalized) == 0:
            raise error_type(f"Expected exactly one {label}.")
        return normalized[0]

    @classmethod
    def required_literal(
        cls,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        error_type: Type[ContainerAttachError],
        label: str,
    ) -> str:
        value: Any = cls.required_object(
            graph,
            subject,
            predicate,
            error_type,
            label,
        )
        if not isinstance(value, Literal):
            raise error_type(f"Expected {label} to be a literal.")
        return str(value).strip()

    @classmethod
    def required_uri(
        cls,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        error_type: Type[ContainerAttachError],
        label: str,
    ) -> str:
        value: Any = cls.required_object(
            graph,
            subject,
            predicate,
            error_type,
            label,
        )
        if not isinstance(value, URIRef):
            raise error_type(f"Expected {label} to be a URI.")
        return str(value).strip()

    @classmethod
    def rewrite_graph(
        cls,
        graph: Graph,
        mapping: Dict[URIRef, URIRef],
    ) -> Graph:
        rewritten: Graph = Graph()
        for prefix, namespace in graph.namespaces():
            rewritten.bind(prefix, namespace)
        rewritten.bind("dcterms", DCTERMS)
        rewritten.bind("ct", AttachmentGraphNamespaceBootstrap.CT)
        rewritten.bind("prov", PROV)
        rewritten.bind("xsd", XSD)
        rewritten.bind("obdc", AttachmentGraphNamespaceBootstrap.OBDC)
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

    @classmethod
    def set_single(
        cls,
        graph: Graph,
        subject: URIRef,
        predicate: URIRef,
        object_value: Any,
    ) -> None:
        graph.remove((subject, predicate, None))
        graph.add((subject, predicate, _to_rdflib_object(object_value)))

    @classmethod
    def remove_subject(cls, graph: Graph, subject: URIRef) -> None:
        for predicate, object_value in list(graph.predicate_objects(subject)):
            graph.remove((subject, predicate, object_value))
        for source, predicate in list(graph.subject_predicates(subject)):
            graph.remove((source, predicate, subject))

    @classmethod
    def matching_container_subjects(
        cls,
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
        obdc = AttachmentGraphNamespaceBootstrap.OBDC
        for subject in graph.subjects(RDF.type, obdc.DataContainer):
            if not isinstance(subject, URIRef) or subject in subjects:
                continue
            identifiers: Set[str] = {
                str(value).strip()
                for value in graph.objects(subject, DCTERMS.identifier)
            }
            locations: Set[str] = {
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
