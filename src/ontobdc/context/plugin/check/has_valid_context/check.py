import os
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.shared.adapter.config import ConfigDataAdapter, UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter

_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")
BASE_CONTEXT_URI = URIRef("urn:ontobdc:context/CurrentContext")


def _get_context_file_path(root_path: Optional[str] = None) -> Path:
    if isinstance(root_path, str) and root_path.strip():
        return Path(root_path).expanduser().resolve() / ".__ontobdc__" / "context.ttl"

    config_adapter: ConfigDataAdapter = ConfigDataAdapter()
    return config_adapter.config_dir / "context.ttl"


def main(root_path: Optional[str] = None) -> int:
    try:
        context_file_path: Path = _get_context_file_path(root_path=root_path)
        if not os.path.isfile(context_file_path):
            return 1

        graph: Graph = Graph()
        graph.parse(context_file_path, format="turtle")

        context_reference: URIRef = BASE_CONTEXT_URI
        if (context_reference, RDF.type, OBDC.ExecutionContext) not in graph:
            return 1

        if (context_reference, OBDC.contextLanguage, None) not in graph:
            return 1

        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
