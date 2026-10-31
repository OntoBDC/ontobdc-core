from pathlib import Path
from typing import Optional, Tuple

from pyshacl import validate
from pyshacl.errors import (
    ConstraintLoadError,
    ReportableRuntimeError,
    RuleLoadError,
    ShapeLoadError,
)
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from ontobdc.shared.adapter.ontology import BrasidataCenterOntologyLibrary

FACADE: Namespace = Namespace(
    "http://datacenter.app.br/ontology/tool/ontobdc/facade/ns.ttl#"
)

# brasidatacenter commit 6d9e604 split the old single-file
# tbox/facade.ttl into a facade/ directory (ns.ttl, data_container.ttl,
# annotation.ttl); the shapes this check needs stayed in ns.ttl under
# the ontology's own, still-unchanged owl:Ontology IRI, so only the
# physical path brasidatacenter.resources resolves from moved.
FACADE_SHAPES_IRI: str = "http://datacenter.app.br/ontology/tool/ontobdc/facade/ns.ttl"

FACADE_FILE_NAME: str = "dataset_facade.ttl"
LINKSET_DIRECTORY_NAME: str = "linkset"
PAYLOAD_DIRECTORY_NAME: str = "payload"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _load_graph(file_path: Path) -> Tuple[Optional[Graph], Optional[str]]:
    """The graph of the file, or why it could not be read."""
    graph: Graph = Graph()
    try:
        graph.parse(str(file_path), format="turtle")
    except Exception as error:
        return None, f"{file_path} cannot be read as Turtle: {type(error).__name__}: {error}"

    return graph, None


def _load_shapes_graph() -> Graph:
    """
    The SHACL shapes every dataset facade must conform to.

    Raises:
        FileNotFoundError: the installed ontologies have none at
            ``FACADE_SHAPES_IRI``; no dataset can be judged without them.
    """
    return BrasidataCenterOntologyLibrary().graph(FACADE_SHAPES_IRI)


def _declares_facade(facade_graph: Graph) -> bool:
    return any(
        True
        for _ in facade_graph.subjects(
            RDF.type,
            FACADE.DataEntityFacade,
        )
    )


def _shapes_problem(
    facade_graph: Graph,
    shapes_graph: Graph,
) -> Optional[str]:
    """Why the facade does not conform to the shapes, or None when it does."""
    try:
        validation_result: Tuple[bool, object, str] = validate(
            data_graph=facade_graph,
            shacl_graph=shapes_graph,
            inference="rdfs",
        )
    except (
        ConstraintLoadError,
        ReportableRuntimeError,
        RuleLoadError,
        ShapeLoadError,
        RuntimeError,
    ) as error:
        return f"the shapes could not be checked: {type(error).__name__}: {error}"

    if validation_result[0]:
        return None
    return f"the facade does not conform to the shapes: {' '.join(str(validation_result[2]).split())[:400]}"


def problem(dataset_path: Optional[str] = None) -> Optional[str]:
    """What keeps the dataset from having a valid facade, in words; None when it has one."""
    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return "the dataset is not a directory"

    facade_path: Path = (
        resolved_dataset_path
        / PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / FACADE_FILE_NAME
    )
    if not facade_path.is_file():
        return f"there is no facade at {facade_path}"

    facade_graph, unreadable = _load_graph(facade_path)
    if facade_graph is None:
        return unreadable

    if not _declares_facade(facade_graph):
        return f"{facade_path} declares no facade"

    return _shapes_problem(facade_graph, _load_shapes_graph())


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 when payload/linkset/dataset_facade.ttl exists and conforms
    to the SHACL shapes declared by the canonical facade ontology.
    """
    del root_path

    return 0 if problem(dataset_path) is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
