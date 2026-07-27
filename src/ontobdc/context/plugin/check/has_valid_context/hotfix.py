from pathlib import Path
from typing import Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, Namespace

from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter

DEFAULT_CONTEXT_LANGUAGE: str = "en"
BASE_CONTEXT_URI: Namespace = Namespace("urn:ontobdc:context/")
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


def _get_context_file_path(root_path: Optional[str] = None) -> Path:
    if isinstance(root_path, str) and root_path.strip():
        return Path(root_path).expanduser().resolve() / ".__ontobdc__" / "context.ttl"

    config_adapter: ConfigDataAdapter = ConfigDataAdapter()
    return config_adapter.config_dir / "context.ttl"


def _build_context_graph(
    root_path: Path,
    language: str = DEFAULT_CONTEXT_LANGUAGE,
) -> Graph:
    graph: Graph = Graph()
    graph.bind("", BASE_CONTEXT_URI)
    graph.bind("obdc", OBDC)
    graph.bind("owl", OWL)

    context_reference: URIRef = BASE_CONTEXT_URI["CurrentContext"]
    graph.add((context_reference, RDF.type, OBDC.ExecutionContext))
    graph.add((context_reference, RDF.type, OWL.NamedIndividual))
    graph.add((context_reference, OBDC.contextLanguage, Literal(language)))
    graph.add((context_reference, OBDC.projectRootLocation, URIRef(root_path.as_uri())))
    return graph

def main(root_path: Optional[str] = None) -> int:
    try:
        context_file_path: Path = _get_context_file_path(root_path=root_path)
        context_file_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_root_path: Path = context_file_path.parent.parent.resolve()
        context_graph: Graph = _build_context_graph(resolved_root_path)
        context_graph.serialize(destination=context_file_path, format="turtle")
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
