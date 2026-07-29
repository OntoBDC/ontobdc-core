from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, XSD, Namespace

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage import get_storage_file

STORAGE_IDENTIFIER: str = "urn:ontobdc:storage/local"
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")
CT: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("ct")
PROV: Namespace = _ontology_adapter.get_ontology_namespace_by_prefix("prov")


def _build_storage_graph(root_path: Path) -> Graph:
    graph: Graph = Graph()
    graph.bind("dcterms", DCTERMS)
    graph.bind("ct", CT)
    graph.bind("prov", PROV)
    graph.bind("xsd", XSD)
    graph.bind("obdc", OBDC)

    storage_reference: URIRef = URIRef(STORAGE_IDENTIFIER)
    created_at: Literal = Literal(
        datetime.now(timezone.utc).isoformat(),
        datatype=XSD.dateTime,
    )
    title: Literal = Literal("The Main Storage Index", lang="en")
    description: Literal = Literal(
        f"Main storage container for project at {root_path.name or root_path.as_posix()}",
        lang="en",
    )

    graph.add((storage_reference, RDF.type, OBDC.DataStorage))
    graph.add((storage_reference, DCTERMS.identifier, Literal(STORAGE_IDENTIFIER)))
    graph.add((storage_reference, DCTERMS.title, title))
    graph.add((storage_reference, CT.creationDate, created_at))
    graph.add((storage_reference, CT.description, description))
    graph.add((storage_reference, PROV.atLocation, URIRef(root_path.as_uri())))
    return graph

def main(root_path: Optional[str] = None) -> int:
    try:
        storage_file_path: Path = Path(get_storage_file(root_path=root_path))
        storage_file_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_root_path: Path = storage_file_path.parent.parent.resolve()
        storage_graph: Graph = _build_storage_graph(resolved_root_path)
        storage_graph.serialize(destination=storage_file_path, format="turtle")
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
