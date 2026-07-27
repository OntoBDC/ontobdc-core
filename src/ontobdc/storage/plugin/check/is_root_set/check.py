import os
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.adapter.config import UnsetProjectRootConfigDataAdapter
from ontobdc.shared.adapter.ontology import OntologyConfigAdapter
from ontobdc.storage import get_storage_file

STORAGE_IDENTIFIER: str = "urn:ontobdc:storage/local"
_ontology_adapter: OntologyConfigAdapter = OntologyConfigAdapter(
    config_adapter=UnsetProjectRootConfigDataAdapter(),
)
OBDC = _ontology_adapter.get_ontology_namespace_by_prefix("obdc")


def main(root_path: Optional[str] = None) -> int:
    try:
        storage_file_path: Path = Path(get_storage_file(root_path=root_path))
        if not os.path.isfile(storage_file_path):
            return 1

        graph: Graph = Graph()
        graph.parse(storage_file_path, format="turtle")

        storage_reference: URIRef = URIRef(STORAGE_IDENTIFIER)
        if (storage_reference, RDF.type, OBDC.DataStorage) not in graph:
            return 1

        if (storage_reference, DCTERMS.identifier, None) not in graph:
            return 1

        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
