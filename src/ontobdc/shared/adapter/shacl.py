from typing import Any, ClassVar, List, Optional, Tuple

from rdflib import Graph, Literal, URIRef
from pyshacl import validate
from rdflib.term import Node
from rdflib.namespace import RDF, SH

from ontobdc.shared.domain.model.shacl import ShaclViolation, ShaclValidationReport


class ShaclValidator:
    """
    Validate a data graph against a shapes graph with pySHACL.

    The validation itself is pySHACL's; this adapter only reads its
    ValidationReport into the focus node, shape, path, constraint component
    and message of each result. A result produced by a property shape is
    reported with the node shape that declares it, which is the shape a
    reader looks up in the shapes file.
    """

    MESSAGE_LANGUAGE: ClassVar[str] = "en"

    @classmethod
    def validate(cls, data: Graph, shapes: Graph) -> ShaclValidationReport:
        result: Tuple[bool, Graph, str] = validate(
            data_graph=data,
            shacl_graph=shapes,
            inference="none",
            abort_on_first=False,
        )
        conforms: bool = result[0]
        report: Graph = result[1]
        return ShaclValidationReport(
            conforms=conforms,
            violations=tuple(
                cls._violation(report, shapes, node)
                for node in report.subjects(RDF.type, SH.ValidationResult)
            ),
            text=result[2],
        )

    @classmethod
    def _violation(cls, report: Graph, shapes: Graph, result: Node) -> ShaclViolation:
        return ShaclViolation(
            focus_node=cls._value(report, result, SH.focusNode),
            shape=cls._shape(report, shapes, result),
            path=cls._value(report, result, SH.resultPath),
            constraint=cls._value(report, result, SH.sourceConstraintComponent),
            message=cls._message(report, result),
        )

    @classmethod
    def _shape(cls, report: Graph, shapes: Graph, result: Node) -> Optional[str]:
        source: Optional[Node] = report.value(result, SH.sourceShape)
        if source is None:
            return None
        declaring: Optional[Node] = shapes.value(predicate=SH.property, object=source)
        if isinstance(declaring, URIRef):
            return str(declaring)
        if isinstance(source, URIRef):
            return str(source)
        return None

    @classmethod
    def _message(cls, report: Graph, result: Node) -> Optional[str]:
        messages: List[Any] = list(report.objects(result, SH.resultMessage))
        if not messages:
            return None
        preferred: List[Any] = [
            message
            for message in messages
            if isinstance(message, Literal) and message.language == cls.MESSAGE_LANGUAGE
        ]
        return str(preferred[0] if preferred else messages[0])

    @staticmethod
    def _value(report: Graph, result: Node, predicate: URIRef) -> Optional[str]:
        value: Optional[Node] = report.value(result, predicate)
        if value is None:
            return None
        return str(value)
