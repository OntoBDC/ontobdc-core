from typing import Any, Dict, List

from brasidatacenter.tool.adapter.entity_info import entity_info
from rdflib import Graph

from ontobdc.container.adapter.entity_tree import ContainerEntityTree, PropertyPathEvaluator
from ontobdc.container.adapter.ontology_axioms import OntologyAxioms

P = "http://datacenter.app.br/ontology/domain/productivity/taxonomy/type.ttl#"
GOAL, PLAN, STEP = f"{P}Goal", f"{P}Plan", f"{P}Step"
PREFIXES = f"""@prefix p: <{P}> .
@prefix ex: <urn:ex:> .
@prefix pplan: <http://purl.org/net/p-plan#> .
"""


def graph_of(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=PREFIXES + turtle, format="turtle")
    return graph


def entity(iri: str, name: str, kind: str, dataset: str) -> Dict[str, Any]:
    return {"iri": iri, "global_id": name.lower(), "name": name, "type": kind, "dataset": dataset}


def productivity_children_of(class_iri: str) -> List[Dict[str, Any]]:
    """What the facades of BrasidataCenter say: the tree is whatever they declare."""
    info = entity_info(class_iri)
    return list(info["tree_children"]) if info else []


def tree_of(turtle: str, entities: List[Dict[str, Any]], roots: List[Dict[str, Any]], root_class: str = GOAL):
    return ContainerEntityTree(
        graph_of(turtle),
        {item["iri"]: item for item in entities},
        OntologyAxioms.load(),
        productivity_children_of,
    ).nodes(root_class, roots)


def shape(nodes: List[Dict[str, Any]]) -> List[Any]:
    return [(node["name"], shape(node["children"])) for node in nodes]


GOAL_A = entity("urn:ex:goalA", "Goal A", "Goal", "goals")
GOAL_B = entity("urn:ex:goalB", "Goal B", "Goal", "goals")
PLAN_A = entity("urn:ex:planA", "Plan A", "Plan", "plans")
PLAN_B = entity("urn:ex:planB", "Plan B", "Plan", "plans")
PLAN_C = entity("urn:ex:planC", "Plan C", "Plan", "plans")
STEP_A1 = entity("urn:ex:stepA1", "Step A1", "Step", "steps")
STEP_A2 = entity("urn:ex:stepA2", "Step A2", "Step", "steps")
STEP_B1 = entity("urn:ex:stepB1", "Step B1", "Step", "steps")
EVERYTHING = [GOAL_A, GOAL_B, PLAN_A, PLAN_B, PLAN_C, STEP_A1, STEP_A2, STEP_B1]


def test_the_facades_declare_the_levels_and_the_leaf():
    assert [(c["entity_iri"], c["path"]) for c in productivity_children_of(GOAL)] == [(PLAN, {"predicate": f"{P}hasPlan"})]
    assert [(c["entity_iri"], c["path"]) for c in productivity_children_of(PLAN)] == [(STEP, {"predicate": f"{P}hasStep"})]
    assert productivity_children_of(STEP) == []


def test_a_goal_with_two_plans_each_with_its_own_steps():
    nodes = tree_of(
        """
        ex:goalA a p:Goal ; p:hasPlan ex:planA , ex:planB .
        ex:planA a p:Plan ; p:hasStep ex:stepA1 , ex:stepA2 .
        ex:planB a p:Plan ; p:hasStep ex:stepB1 .
        ex:stepA1 a p:Step . ex:stepA2 a p:Step . ex:stepB1 a p:Step .
        """,
        EVERYTHING,
        [GOAL_A],
    )
    assert shape(nodes) == [("Goal A", [("Plan A", [("Step A1", []), ("Step A2", [])]), ("Plan B", [("Step B1", [])])])]


def test_a_goal_without_plans_is_a_leaf():
    nodes = tree_of("ex:goalA a p:Goal .", EVERYTHING, [GOAL_A])
    assert shape(nodes) == [("Goal A", [])]


def test_a_plan_without_steps_is_a_leaf():
    nodes = tree_of(
        "ex:goalA a p:Goal ; p:hasPlan ex:planA . ex:planA a p:Plan .",
        EVERYTHING,
        [GOAL_A],
    )
    assert shape(nodes) == [("Goal A", [("Plan A", [])])]


def test_two_goals_do_not_share_children():
    nodes = tree_of(
        """
        ex:goalA a p:Goal ; p:hasPlan ex:planA .
        ex:goalB a p:Goal ; p:hasPlan ex:planB , ex:planC .
        ex:planA a p:Plan ; p:hasStep ex:stepA1 .
        ex:planB a p:Plan ; p:hasStep ex:stepB1 .
        ex:planC a p:Plan .
        ex:stepA1 a p:Step . ex:stepB1 a p:Step .
        """,
        EVERYTHING,
        [GOAL_A, GOAL_B],
    )
    assert shape(nodes) == [
        ("Goal A", [("Plan A", [("Step A1", [])])]),
        ("Goal B", [("Plan B", [("Step B1", [])]), ("Plan C", [])]),
    ]


def test_steps_stored_only_as_is_step_of_plan_are_found_through_has_step():
    graph_text = """
        ex:goalA a p:Goal ; p:hasPlan ex:planA .
        ex:planA a p:Plan .
        ex:stepA1 a p:Step ; pplan:isStepOfPlan ex:planA .
        ex:stepA2 a p:Step ; pplan:isStepOfPlan ex:planA .
    """
    graph = graph_of(graph_text)
    assert not list(graph.subject_objects(graph.namespace_manager.expand_curie("p:hasStep")))
    nodes = tree_of(graph_text, EVERYTHING, [GOAL_A])
    assert shape(nodes) == [("Goal A", [("Plan A", [("Step A1", []), ("Step A2", [])])])]


def test_a_facade_without_tree_children_makes_its_entities_leaves():
    tree = ContainerEntityTree(
        graph_of("ex:goalA a p:Goal ; p:hasPlan ex:planA . ex:planA a p:Plan ; p:hasStep ex:stepA1 . ex:stepA1 a p:Step ."),
        {item["iri"]: item for item in EVERYTHING},
        OntologyAxioms.load(),
        lambda class_iri: productivity_children_of(class_iri) if class_iri == GOAL else [],
    )
    assert shape(tree.nodes(GOAL, [GOAL_A])) == [("Goal A", [("Plan A", [])])]


def test_the_depth_is_not_fixed():
    levels = 7
    items = [entity(f"urn:ex:n{i}", f"Level {i}", "Node", "nodes") for i in range(levels)]
    turtle = "\n".join(f"ex:n{i} a ex:Node ; ex:child ex:n{i + 1} ." for i in range(levels - 1)) + f"\nex:n{levels - 1} a ex:Node ."
    declared = [{"facade_iri": "urn:f", "entity_iri": "urn:ex:Node", "path": {"predicate": "urn:ex:child"}}]
    tree = ContainerEntityTree(graph_of(turtle), {i["iri"]: i for i in items}, OntologyAxioms({}, {}), lambda _: declared)
    node = tree.nodes("urn:ex:Node", [items[0]])[0]
    depth = 1
    while node["children"]:
        node = node["children"][0]
        depth += 1
    assert depth == levels


def test_nodes_of_different_datasets_keep_their_own_dataset():
    nodes = tree_of(
        "ex:goalA a p:Goal ; p:hasPlan ex:planA . ex:planA a p:Plan ; p:hasStep ex:stepA1 . ex:stepA1 a p:Step .",
        EVERYTHING,
        [GOAL_A],
    )
    goal = nodes[0]
    plan = goal["children"][0]
    step = plan["children"][0]
    assert (goal["dataset"], plan["dataset"], step["dataset"]) == ("goals", "plans", "steps")
    assert (goal["iri"], plan["iri"], step["iri"]) == ("urn:ex:goalA", "urn:ex:planA", "urn:ex:stepA1")


def test_a_resource_that_is_not_kept_as_an_entity_or_is_of_another_class_is_not_a_child():
    nodes = tree_of(
        """
        ex:goalA a p:Goal ; p:hasPlan ex:planA , ex:ghost , ex:goalB .
        ex:planA a p:Plan .
        ex:goalB a p:Goal .
        """,
        EVERYTHING,
        [GOAL_A],
    )
    assert shape(nodes) == [("Goal A", [("Plan A", [])])]


def test_a_cycle_is_cut_where_it_closes():
    items = [entity("urn:ex:a", "A", "Node", "nodes"), entity("urn:ex:b", "B", "Node", "nodes")]
    declared = [{"facade_iri": "urn:f", "entity_iri": "urn:ex:Node", "path": {"predicate": "urn:ex:child"}}]
    tree = ContainerEntityTree(
        graph_of("ex:a a ex:Node ; ex:child ex:b , ex:a . ex:b a ex:Node ; ex:child ex:a ."),
        {i["iri"]: i for i in items},
        OntologyAxioms({}, {}),
        lambda _: declared,
    )
    assert shape(tree.nodes("urn:ex:Node", [items[0]])) == [("A", [("B", [])])]


def test_property_paths_of_the_shacl_kinds_are_evaluated():
    graph = graph_of("ex:a ex:p ex:b . ex:b ex:q ex:c . ex:c ex:p ex:d . ex:x ex:p ex:b .")
    paths = PropertyPathEvaluator(graph, OntologyAxioms({}, {}))
    a = {"predicate": "urn:ex:p"}
    b = {"predicate": "urn:ex:q"}

    def reached(path: Dict[str, Any], *start: str) -> List[str]:
        from rdflib import URIRef
        return sorted(str(node) for node in paths.evaluate(path, {URIRef(s) for s in start}))

    assert reached(a, "urn:ex:a") == ["urn:ex:b"]
    assert reached({"inverse": a}, "urn:ex:b") == ["urn:ex:a", "urn:ex:x"]
    assert reached({"sequence": [a, b]}, "urn:ex:a") == ["urn:ex:c"]
    assert reached({"inverse": {"sequence": [a, b]}}, "urn:ex:c") == ["urn:ex:a", "urn:ex:x"]
    assert reached({"alternative": [a, b]}, "urn:ex:a", "urn:ex:b") == ["urn:ex:b", "urn:ex:c"]
    assert reached({"zeroOrMore": {"alternative": [a, b]}}, "urn:ex:a") == ["urn:ex:a", "urn:ex:b", "urn:ex:c", "urn:ex:d"]
    assert reached({"oneOrMore": {"alternative": [a, b]}}, "urn:ex:a") == ["urn:ex:b", "urn:ex:c", "urn:ex:d"]
    assert reached({"zeroOrOne": a}, "urn:ex:a") == ["urn:ex:a", "urn:ex:b"]


def test_the_ontology_gives_the_inverse_the_tree_relies_on():
    axioms = OntologyAxioms.load()
    assert "http://purl.org/net/p-plan#isStepOfPlan" in axioms.inverses_of(f"{P}hasStep")
    assert f"{P}hasStep" in axioms.inverses_of("http://purl.org/net/p-plan#isStepOfPlan")
