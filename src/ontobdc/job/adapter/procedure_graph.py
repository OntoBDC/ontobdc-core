from typing import Any, Dict, List, Optional

from brasidatacenter.resources import iter_ontology_files
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, SH

from ontobdc.shared.adapter.shacl import ShaclValidator
from ontobdc.shared.domain.model.shacl import ShaclValidationReport
from ontobdc.shared.domain.vocabulary import OBDC, PKO


class ProcedureGraph:
    """
    A procedure of a graph that comes from anywhere: found by the name of its node, tested against the
    shape of a procedure, and read for the id of what it executes.
    """

    SHAPE_FILE: str = "procedure_shape.ttl"
    SHAPE: URIRef = URIRef(
        "http://datacenter.app.br/ontology/tool/ontobdc/core/procedure_shape.ttl#ProcedureShape"
    )

    @staticmethod
    def node(graph: Graph, name: str) -> URIRef:
        """
        The node of the graph whose local name (what follows the ``#``, or the last ``/``) is the name.

        Raises:
            LookupError: no node has the name, or more than one does.
        """
        nodes: List[URIRef] = sorted(
            {
                subject
                for subject in graph.subjects()
                if isinstance(subject, URIRef) and ProcedureGraph.local_name(subject) == name
            }
        )
        if not nodes:
            raise LookupError(f"The graph has no node named {name}.")
        if len(nodes) > 1:
            raise LookupError(f"More than one node of the graph is named {name}: {', '.join(map(str, nodes))}.")

        return nodes[0]

    @classmethod
    def validate(cls, graph: Graph, node: URIRef) -> None:
        """
        Tests the node against the shape of a procedure.

        Raises:
            ValueError: the node does not conform, and why.
        """
        shapes: Graph = cls._shapes()
        shapes.add((cls.SHAPE, SH.targetNode, node))
        report: ShaclValidationReport = ShaclValidator.validate(cls.snapshot(graph, node), shapes)
        if not report.conforms:
            reasons: str = "; ".join(
                violation.message or violation.constraint or "violation" for violation in report.violations
            )
            raise ValueError(f"The procedure <{node}> does not conform to the shape of a procedure: {reasons}")

    @staticmethod
    def snapshot(graph: Graph, node: URIRef) -> Graph:
        """
        What the graph says of the node itself: its concise bounded description, and the one of each variable it
        requires, which is what a job has to be given.
        """
        snapshot: Graph = graph.cbd(node)
        variable: Any
        for variable in graph.objects(node, OBDC.hasRequiredInputVar):
            snapshot += graph.cbd(variable)

        return snapshot

    @staticmethod
    def target(graph: Graph, node: URIRef) -> str:
        """
        The id of what the procedure executes.
        """
        value: Optional[Any] = graph.value(node, PKO.hasProcedureTarget)
        if value is None:
            raise ValueError(f"The procedure <{node}> has no target.")

        return str(value)

    @classmethod
    def required_parameters(cls, graph: Graph, node: URIRef) -> List[Dict[str, str]]:
        """
        The parameters a job needs to be given to execute the procedure: for each variable it requires, the name of
        the parameter (the identifier of the variable), what it is called and what it is, in English when it says so.
        """
        required: List[Dict[str, str]] = []
        variable: Any
        for variable in sorted(graph.objects(node, OBDC.hasRequiredInputVar), key=str):
            name: Any = graph.value(variable, DCTERMS.identifier)
            if name is None:
                raise ValueError(f"The variable <{variable}> the procedure <{node}> requires has no identifier.")

            required.append(
                {
                    "name": str(name),
                    "label": cls._english(graph, variable, RDFS.label) or str(name),
                    "description": cls._english(graph, variable, DCTERMS.description) or "",
                }
            )

        return required

    @staticmethod
    def _english(graph: Graph, subject: Any, predicate: URIRef) -> Optional[str]:
        """The text of the subject under the predicate, in English when it has one, else the first it has."""
        values: List[Any] = list(graph.objects(subject, predicate))
        for value in values:
            if getattr(value, "language", None) == "en":
                return str(value)

        return str(values[0]) if values else None

    @staticmethod
    def label(graph: Graph, node: URIRef) -> Optional[str]:
        """
        The label of the procedure, in English when it has one.
        """
        labels: List[Any] = list(graph.objects(node, RDFS.label))
        for label in labels:
            if getattr(label, "language", None) == "en":
                return str(label)

        return str(labels[0]) if labels else None

    @staticmethod
    def local_name(iri: URIRef) -> str:
        text: str = str(iri)
        return text.rsplit("#", 1)[-1] if "#" in text else text.rstrip("/").rsplit("/", 1)[-1]

    @classmethod
    def _shapes(cls) -> Graph:
        for ontology_file in iter_ontology_files():
            if ontology_file.name == cls.SHAPE_FILE:
                shapes: Graph = Graph()
                shapes.parse(data=ontology_file.read_text(encoding="utf-8"), format="turtle")
                return shapes

        raise ValueError("The shape of a procedure is not part of BrasidataCenter.")
