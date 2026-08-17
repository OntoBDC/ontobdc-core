from pathlib import Path
from typing import Any, Dict, List

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.term import Node


class ContextGraphAdapter:
    """Read the persisted context Turtle file as graph nodes and edges."""

    def load(self, context_file_path: Path) -> Dict[str, Any]:
        graph: Graph = Graph()
        graph.parse(str(context_file_path), format="turtle")

        nodes_by_id: Dict[str, Dict[str, str]] = {}
        edges: List[Dict[str, str]] = []

        subject: Node
        predicate: Node
        obj: Node
        for subject, predicate, obj in sorted(
            graph,
            key=lambda triple: tuple(str(term) for term in triple),
        ):
            source_id: str = self._node_id(subject)
            target_id: str = self._node_id(obj)

            if source_id not in nodes_by_id:
                nodes_by_id[source_id] = self._node(subject, graph)
            if target_id not in nodes_by_id:
                nodes_by_id[target_id] = self._node(obj, graph)

            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "label": self._term_label(predicate, graph),
                }
            )

        return {
            "nodes": list(nodes_by_id.values()),
            "edges": edges,
        }

    def _node(self, term: Node, graph: Graph) -> Dict[str, str]:
        return {
            "id": self._node_id(term),
            "label": self._term_label(term, graph),
            "kind": self._term_kind(term),
        }

    def _node_id(self, term: Node) -> str:
        if isinstance(term, URIRef):
            return f"uri:{term}"
        if isinstance(term, BNode):
            return f"blank:{term}"
        if isinstance(term, Literal):
            return f"literal:{term.n3()}"
        return f"term:{term}"

    def _term_label(self, term: Node, graph: Graph) -> str:
        if isinstance(term, URIRef):
            try:
                return graph.namespace_manager.normalizeUri(term)
            except Exception:
                return str(term)
        if isinstance(term, BNode):
            return f"_:{term}"
        if isinstance(term, Literal):
            return term.n3(namespace_manager=graph.namespace_manager)
        return str(term)

    def _term_kind(self, term: Node) -> str:
        if isinstance(term, URIRef):
            return "uri"
        if isinstance(term, BNode):
            return "blank"
        if isinstance(term, Literal):
            return "literal"
        return "term"
