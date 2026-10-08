from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF

from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageLayoutConstants,
)


def main(root_path: Optional[str] = None) -> int:
    try:
        storage_file = StorageBootstrap.get_storage_file_path(
            StorageBootstrap.get_init_root_path(root_path=root_path)
        )
        if not storage_file.is_file():
            return 1

        graph: Graph = Graph()
        graph.parse(str(storage_file), format="turtle")
        storage: URIRef = URIRef(StorageLayoutConstants.STORAGE_IDENTIFIER)
        if (storage, RDF.type, OBDC.DataStorage) not in graph:
            return 1

        return 0 if (storage, DCTERMS.identifier, None) in graph else 1
    except Exception:
        return 1
