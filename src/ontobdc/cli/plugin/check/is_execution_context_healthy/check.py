from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ontobdc.shared.domain.vocabulary import OBDC
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StorageNamespaceBootstrap,
)


def main(root_path: Optional[str] = None) -> int:
    try:
        context_file = StorageBootstrap.get_context_file_path(
            StorageBootstrap.get_init_root_path(root_path=root_path)
        )
        if not context_file.is_file():
            return 1

        graph: Graph = Graph()
        graph.parse(str(context_file), format="turtle")
        context: URIRef = StorageNamespaceBootstrap.BASE_CONTEXT_URI["CurrentContext"]
        if (context, RDF.type, OBDC.ExecutionContext) not in graph:
            return 1

        return 0 if (context, OBDC.contextLanguage, None) in graph else 1
    except Exception:
        return 1
