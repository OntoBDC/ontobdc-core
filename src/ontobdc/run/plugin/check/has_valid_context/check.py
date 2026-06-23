
import os
import sys
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.adapter.ontology import get_ontology_by_prefix

OBDC: Namespace = get_ontology_by_prefix("obdc")
BASE_URI: Namespace = Namespace("urn:ontobdc:context/")


def main(print_log: callable = None) -> int:
    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Check Valid Context", message)

    try:
        context_file: str = str(ConfigDataAdapter().config_dir / "context.ttl")

        if not os.path.exists(context_file):
            _print_error_log(f"Context file not found: {context_file}", print_log)
            return 1

        graph: Graph = Graph()
        graph.parse(context_file, format="turtle")

        # Check if there's an ExecutionContext individual
        context_individual = None
        for s in graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            context_individual = s
            break

        if not isinstance(context_individual, URIRef):
            _print_error_log("No valid ExecutionContext individual found in context graph.", print_log)
            return 1

        return 0
    except Exception as e:
        _print_error_log(f"Error checking context: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
