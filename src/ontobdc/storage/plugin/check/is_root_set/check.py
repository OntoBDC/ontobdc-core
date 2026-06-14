
import os
import sys
from typing import Optional
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS, RDF
from ontobdc.storage import get_storage_file
from ontobdc.storage.adapter.repository import LoadedStorageGraph
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix
from ontobdc.storage.domain.port.repository import LoadedStorageGraphPort

CT = get_ontology_by_prefix("ct")


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Root Container", message)
        else:
            print(message, file=sys.stderr)


    try:
        storage_file_path: str = get_storage_file()

        if not os.path.exists(storage_file_path):
            _print_error_log("Storage configuration file not found.", print_log)
            return 1

        root_graph: LoadedStorageGraphPort = LoadedStorageGraph(storage_file_path)
        root_container: Optional[URIRef] = root_graph.get_root_container()

        if not isinstance(root_container, URIRef):
            _print_error_log("Root container not found in storage graph.", print_log)
            return 1

        return 0
    except Exception as e:
        _print_error_log(f"Invalid storage configuration: {str(e)}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
