from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, List, Optional, Set

from brasidatacenter.tool.adapter.entity_info import entity_info
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.container.adapter.ontology_axioms import OntologyAxioms


class PropertyPathEvaluator:
    """
    Evaluates a SHACL property path, as ``entity_info`` gives it as data, from
    a set of resources: a predicate, ``inverse``, ``sequence``,
    ``alternative``, ``zeroOrMore``, ``oneOrMore`` and ``zeroOrOne``. A
    predicate is followed in both senses its inverses allow: a graph that says
    only ``step isStepOfPlan plan`` answers ``plan hasStep ?`` too, without the
    inverse triple being written anywhere.
    """

    def __init__(self, graph: Graph, axioms: OntologyAxioms) -> None:
        self._graph: Graph = graph
        self._axioms: OntologyAxioms = axioms

    def evaluate(self, path: Dict[str, Any], start: Set[URIRef]) -> Set[URIRef]:
        if "predicate" in path:
            return self._follow(path["predicate"], start, forward=True)
        if "inverse" in path:
            inner: Dict[str, Any] = path["inverse"]
            if "predicate" in inner:
                return self._follow(inner["predicate"], start, forward=False)
            return self.evaluate(self._invert(inner), start)
        if "sequence" in path:
            reached: Set[URIRef] = start
            step: Dict[str, Any]
            for step in path["sequence"]:
                reached = self.evaluate(step, reached)
            return reached
        if "alternative" in path:
            found: Set[URIRef] = set()
            for step in path["alternative"]:
                found |= self.evaluate(step, start)
            return found
        if "zeroOrOne" in path:
            return start | self.evaluate(path["zeroOrOne"], start)
        if "zeroOrMore" in path:
            return self._closure(path["zeroOrMore"], start, include_start=True)
        if "oneOrMore" in path:
            return self._closure(path["oneOrMore"], start, include_start=False)

        raise ValueError(f"Unknown property path: {path!r}")

    def _closure(self, path: Dict[str, Any], start: Set[URIRef], include_start: bool) -> Set[URIRef]:
        reached: Set[URIRef] = set(start) if include_start else set()
        frontier: Set[URIRef] = set(start)
        while frontier:
            frontier = self.evaluate(path, frontier) - reached
            reached |= frontier

        return reached

    @classmethod
    def _invert(cls, path: Dict[str, Any]) -> Dict[str, Any]:
        if "predicate" in path:
            return {"inverse": path}
        if "inverse" in path:
            return path["inverse"]
        if "sequence" in path:
            return {"sequence": [cls._invert(step) for step in reversed(path["sequence"])]}
        if "alternative" in path:
            return {"alternative": [cls._invert(step) for step in path["alternative"]]}
        kind: str
        for kind in ("zeroOrOne", "zeroOrMore", "oneOrMore"):
            if kind in path:
                return {kind: cls._invert(path[kind])}

        raise ValueError(f"Unknown property path: {path!r}")

    def _follow(self, predicate: str, start: Set[URIRef], forward: bool) -> Set[URIRef]:
        # The inverse of the property says the same thing the other way round.
        names: List[str] = [predicate, *sorted(self._axioms.inverses_of(predicate))]
        found: Set[URIRef] = set()
        node: URIRef
        for node in start:
            for index, name in enumerate(names):
                direct: bool = forward if index == 0 else not forward
                if direct:
                    found.update(o for o in self._graph.objects(node, URIRef(name)) if isinstance(o, URIRef))
                else:
                    found.update(s for s in self._graph.subjects(URIRef(name), node) if isinstance(s, URIRef))

        return found


class ContainerEntityTree:
    """
    The entities of one type of a container, each with the entities below it.

    What is below an entity is not decided here: the facade of its type says it
    (``facade:hasTreeViewChild``: the facade of the children and the property
    path that leads to them) and the same goes for each child, down to a facade
    that says nothing, whose entities are leaves. The children are the
    resources the path reaches in what the data sources of all the datasets
    say, that are kept as entities and are of the class the child facade is of.
    No relation is guessed from names, titles or the place of an entity, and
    an entity already above a node is never below it again.
    """

    ENTITY_INFO_CHILDREN: ClassVar[str] = "tree_children"

    def __init__(
        self,
        graph: Graph,
        entities: Dict[str, Dict[str, Any]],
        axioms: OntologyAxioms,
        tree_children_of: Callable[[str], List[Dict[str, Any]]],
    ) -> None:
        self._graph: Graph = graph
        self._entities: Dict[str, Dict[str, Any]] = entities
        self._axioms: OntologyAxioms = axioms
        self._tree_children_of: Callable[[str], List[Dict[str, Any]]] = tree_children_of
        self._paths: PropertyPathEvaluator = PropertyPathEvaluator(graph, axioms)

    @classmethod
    def of(cls, container_path: Path, entity_iri: str) -> List[Dict[str, Any]]:
        """
        The nodes of the entities of ``entity_iri`` the datasets of the
        container hold, each with its ``children``.
        """
        container: Path = container_path.expanduser().resolve()
        datasets: List[Dict[str, Any]] = ContainerEntities.of(container)
        known: Dict[str, Dict[str, Any]] = {}
        dataset: Dict[str, Any]
        entity: Dict[str, Any]
        for dataset in datasets:
            for entity in dataset["entities"]:
                if entity.get("iri") and entity["iri"] not in known:
                    known[entity["iri"]] = {**entity, "dataset": dataset["path"]}

        cache: Dict[str, List[Dict[str, Any]]] = {}

        def tree_children_of(class_iri: str) -> List[Dict[str, Any]]:
            if class_iri not in cache:
                info: Optional[Dict[str, Any]] = entity_info(class_iri)
                cache[class_iri] = list(info[cls.ENTITY_INFO_CHILDREN]) if info else []

            return cache[class_iri]

        tree: "ContainerEntityTree" = cls(
            ContainerEntities.triples(container), known, OntologyAxioms.load(), tree_children_of
        )
        roots: List[Dict[str, Any]] = [
            {**entity, "dataset": dataset["path"]}
            for dataset in datasets
            if entity_iri in dataset["entity_types"]
            for entity in dataset["entities"]
        ]
        return tree.nodes(entity_iri, roots)

    def nodes(self, entity_iri: str, roots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self._node(root, entity_iri, frozenset()) for root in roots]

    def _node(self, entity: Dict[str, Any], class_iri: str, above: "frozenset[str]") -> Dict[str, Any]:
        iri: Optional[str] = entity.get("iri")
        children: List[Dict[str, Any]] = []
        if iri:
            children = self._children(iri, class_iri, above | {iri})

        return {
            "iri": iri,
            "global_id": entity["global_id"],
            "name": entity["name"],
            "type": entity["type"],
            "dataset": entity["dataset"],
            "children": children,
        }

    def _children(self, iri: str, class_iri: str, above: "frozenset[str]") -> List[Dict[str, Any]]:
        children: Dict[str, Dict[str, Any]] = {}
        declared: Dict[str, Any]
        for declared in self._tree_children_of(class_iri):
            child_class: Optional[str] = declared["entity_iri"]
            if not child_class:
                continue

            reached: Set[URIRef] = self._paths.evaluate(declared["path"], {URIRef(iri)})
            found: URIRef
            for found in sorted(reached, key=str):
                key: str = str(found)
                entity: Optional[Dict[str, Any]] = self._entities.get(key)
                if key in above or key in children or entity is None or not self._is_a(found, child_class):
                    continue

                children[key] = self._node(entity, child_class, above)

        return sorted(children.values(), key=lambda node: (node["name"].casefold(), str(node["iri"])))

    def _is_a(self, resource: URIRef, class_iri: str) -> bool:
        return any(
            self._axioms.is_a(str(declared), class_iri)
            for declared in self._graph.objects(resource, RDF.type)
        )
