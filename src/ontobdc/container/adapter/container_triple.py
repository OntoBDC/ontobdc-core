from pathlib import Path
from typing import ClassVar, Dict, List, Tuple

from rdflib import Graph
from rdflib.plugins.parsers.notation3 import BadSyntax
from rdflib.term import Node



class ContainerTriple:
    """
    One triple of an ontology, written in the ``container.ttl`` of a container.

    It is given as three terms separated by ``;``, always in the order subject, predicate, object. A term is written as
    in Turtle: a full IRI between ``<`` and ``>``, a name with a prefix (``vcard:fn``) or, for the object, a literal
    (``"text"``, ``"text"@pt-br``, ``"1"^^xsd:integer``).

    A prefix has to be one the ``container.ttl`` already declares: any other is an error. A full IRI needs no prefix, and
    its namespace is written in the file as it is.
    """

    SEPARATOR: ClassVar[str] = ";"
    TERMS: ClassVar[int] = 3

    @classmethod
    def split(cls, text: str, minimum: int = TERMS, maximum: int = TERMS) -> List[str]:
        """
        The terms of the text, from the subject on. A ``;`` inside a literal or inside an IRI is not a separator.

        Raises:
            ValueError: the text has fewer terms than the minimum or more than the maximum, or a term is empty.
        """
        terms: List[str] = []
        current: List[str] = []
        quoted: bool = False
        escaped: bool = False
        bracketed: bool = False
        character: str
        for character in text:
            if quoted:
                current.append(character)
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
                continue

            if bracketed:
                current.append(character)
                if character == ">":
                    bracketed = False
                continue

            if character == cls.SEPARATOR:
                terms.append("".join(current).strip())
                current = []
                continue

            quoted = character == '"'
            bracketed = character == "<"
            current.append(character)

        terms.append("".join(current).strip())
        if not minimum <= len(terms) <= maximum or not all(terms):
            expected: str = str(minimum) if minimum == maximum else f"{minimum} to {maximum}"
            raise ValueError(
                f"Expected {expected} terms separated by '{cls.SEPARATOR}', in the order subject, predicate, object: "
                f"got {text!r}."
            )

        return terms

    @classmethod
    def find(cls, file: Path, text: str) -> Tuple[str, Dict[str, List[str]]]:
        """
        What a Turtle file, such as the ``container.ttl`` of a container, says of a subject: the subject, or the subject
        and the predicate, as the text gives them. It maps each predicate to its objects, every term written as in Turtle,
        with the prefixes of the file. With the subject alone, it has every predicate of the subject; with the predicate
        too, only that one. What the file does not say is not in it: nothing says nothing.

        Raises:
            ValueError: the text has more than two terms, or a term is no IRI or name with a declared prefix.
            FileNotFoundError: the file does not exist.
        """
        terms: List[str] = cls.split(text, 1, 2)
        graph: Graph = cls._graph(file)
        subject: Node = cls._node(graph, terms[0])
        predicates: List[Node] = (
            [cls._node(graph, terms[1])] if len(terms) == 2 else sorted(set(graph.predicates(subject)))
        )

        found: Dict[str, List[str]] = {}
        predicate: Node
        for predicate in predicates:
            objects: List[str] = sorted(node.n3(graph.namespace_manager) for node in graph.objects(subject, predicate))
            if objects:
                found[predicate.n3(graph.namespace_manager)] = objects

        return subject.n3(graph.namespace_manager), found

    @classmethod
    def resolve(cls, file: Path, term: str) -> str:
        """
        The IRI a term names, written as in Turtle, with the prefixes of the file.

        Raises:
            ValueError: the term is no IRI, or uses a prefix the file does not declare.
            FileNotFoundError: the file does not exist.
        """
        return str(cls._node(cls._graph(file), term))

    @staticmethod
    def _graph(file: Path) -> Graph:
        if not file.is_file():
            raise FileNotFoundError(f"The file does not exist: {file}")

        graph: Graph = Graph(bind_namespaces="none")
        graph.parse(str(file), format="turtle")
        return graph

    @staticmethod
    def _node(graph: Graph, term: str) -> Node:
        """The node a term names, with the prefixes the graph declares."""
        prefix: str
        namespace: Node
        declarations: str = "".join(f"@prefix {prefix}: <{namespace}> .\n" for prefix, namespace in graph.namespaces())
        probe: Graph = Graph(bind_namespaces="none")
        try:
            probe.parse(data=f"{declarations}{term} a <urn:ontobdc:probe> .\n", format="turtle")
        except BadSyntax as error:
            raise ValueError(
                f"The term {term!r} is no IRI, or uses a prefix that the container.ttl does not declare "
                f"(declared: {sorted(p for p, _ in graph.namespaces() if p)}): {error}"
            ) from error

        return next(probe.subjects())

    @classmethod
    def write(cls, file: Path, text: str) -> bool:
        """
        Write the triple in a Turtle file, such as the ``container.ttl`` of a container.

        Returns:
            Whether the triple was written: False when the file already had it.

        Raises:
            ValueError: the text is not a triple, or it uses a prefix the file does not declare.
            FileNotFoundError: the file does not exist.
        """
        subject, predicate, value = cls.split(text)
        graph: Graph = cls._graph(file)

        prefix: str
        namespace: Node
        declarations: str = "".join(f"@prefix {prefix}: <{namespace}> .\n" for prefix, namespace in graph.namespaces())
        parsed: Graph = Graph(bind_namespaces="none")
        try:
            parsed.parse(data=f"{declarations}{subject} {predicate} {value} .\n", format="turtle")
        except BadSyntax as error:
            raise ValueError(
                f"The triple {text!r} is not valid, or uses a prefix that {file} does not declare "
                f"(declared: {sorted(p for p, _ in graph.namespaces() if p)}): {error}"
            ) from error

        written: bool = False
        triple: Tuple[Node, Node, Node]
        for triple in parsed:
            if triple not in graph:
                graph.add(triple)
                written = True

        if written:
            file.write_bytes(graph.serialize(format="turtle", encoding="utf-8"))

        return written
