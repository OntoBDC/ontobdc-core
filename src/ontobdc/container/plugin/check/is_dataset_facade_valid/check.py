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

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
FACADE: Namespace = Namespace(
    "http://ontobdc.org/ontology/domain/facade.ttl#"
)

FACADE_FILE_NAME: str = "dataset_facade.ttl"
LINKSET_DIRECTORY_NAME: str = "linkset"
PAYLOAD_DIRECTORY_NAME: str = "payload"


def _resolve_path(path_value: Optional[str]) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()


def _load_graph(file_path: Path) -> Optional[Graph]:
    graph: Graph = Graph()
    try:
        graph.parse(str(file_path), format="turtle")
    except Exception:
        return None

    return graph


def _load_shapes_graph() -> Optional[Graph]:
    try:
        return _ontology_adapter.get_ontology_content(
            prefix="obdc_view",
            type="facade",
        )
    except (FileNotFoundError, OSError, ValueError):
        return None


def _declares_facade(facade_graph: Graph) -> bool:
    return any(
        True
        for _ in facade_graph.subjects(
            RDF.type,
            FACADE.DataEntityFacade,
        )
    )


def _conforms_to_shapes(
    facade_graph: Graph,
    shapes_graph: Graph,
) -> bool:
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
    ):
        return False

    conforms: bool = validation_result[0]
    return conforms


def main(
    dataset_path: Optional[str] = None,
    root_path: Optional[str] = None,
) -> int:
    """Return 0 when payload/linkset/dataset_facade.ttl exists and conforms
    to the SHACL shapes declared by the canonical facade ontology.
    """
    del root_path

    resolved_dataset_path: Optional[Path] = _resolve_path(dataset_path)
    if resolved_dataset_path is None or not resolved_dataset_path.is_dir():
        return 1

    facade_path: Path = (
        resolved_dataset_path
        / PAYLOAD_DIRECTORY_NAME
        / LINKSET_DIRECTORY_NAME
        / FACADE_FILE_NAME
    )
    if not facade_path.is_file():
        return 1

    facade_graph: Optional[Graph] = _load_graph(facade_path)
    if facade_graph is None:
        return 1

    if not _declares_facade(facade_graph):
        return 1

    shapes_graph: Optional[Graph] = _load_shapes_graph()
    if shapes_graph is None:
        return 1

    return 0 if _conforms_to_shapes(facade_graph, shapes_graph) else 1


if __name__ == "__main__":
    raise SystemExit(main())
