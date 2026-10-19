from collections import deque
from functools import lru_cache
from typing import Dict, Set

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDFS

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary


class OntologyAxioms:
    """
    The two things the ontologies say that finding the children of an entity
    needs: which properties are the inverse of which, and which classes are
    subclasses of which.
    """

    def __init__(self, inverses: Dict[str, Set[str]], superclasses: Dict[str, Set[str]]) -> None:
        self._inverses: Dict[str, Set[str]] = inverses
        self._superclasses: Dict[str, Set[str]] = superclasses

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> "OntologyAxioms":
        library: BrasidataCenterOntologyLibrary = BrasidataCenterOntologyLibrary()
        inverses: Dict[str, Set[str]] = {}
        superclasses: Dict[str, Set[str]] = {}
        iri: str
        for iri in library.iris():
            # Reading the text is much faster than parsing the file.
            text: str = library.path(iri).read_text(encoding="utf-8")
            if "inverseOf" not in text and "subClassOf" not in text:
                continue

            graph: Graph = library.graph(iri)
            for left, right in graph.subject_objects(OWL.inverseOf):
                inverses.setdefault(str(left), set()).add(str(right))
                inverses.setdefault(str(right), set()).add(str(left))
            for subclass, parent in graph.subject_objects(RDFS.subClassOf):
                if isinstance(subclass, URIRef) and isinstance(parent, URIRef):
                    superclasses.setdefault(str(subclass), set()).add(str(parent))

        return cls(inverses, superclasses)

    def inverses_of(self, predicate: str) -> Set[str]:
        return self._inverses.get(predicate, set())

    def is_a(self, entity_class: str, ancestor: str) -> bool:
        """Whether ``entity_class`` is ``ancestor`` or one of its subclasses, at any depth."""
        seen: Set[str] = {entity_class}
        pending: "deque[str]" = deque([entity_class])
        while pending:
            current: str = pending.popleft()
            if current == ancestor:
                return True
            for parent in self._superclasses.get(current, set()) - seen:
                seen.add(parent)
                pending.append(parent)

        return False
