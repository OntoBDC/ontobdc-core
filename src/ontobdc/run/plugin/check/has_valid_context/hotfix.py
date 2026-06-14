
import os
import sys
from typing import Optional
from rdflib.namespace import RDF, OWL
from ontobdc.cli import get_config_dir
from rdflib import Graph, Literal, Namespace, URIRef
from ontobdc.shared.adapter.config import ConfigDataAdapter
from ontobdc.shared.domain.port.config import ConfigDataPort
from ontobdc.shared.adapter.ontology import as_literal, get_ontology_by_prefix

OBDC: Namespace = get_ontology_by_prefix("obdc")
BASE_URI: Namespace = Namespace("urn:ontobdc:context/")


def main(print_log: callable = None) -> int:
    def _print_info_log(message: str, print_log: callable = None):
        if print_log:
            print_log("INFO", "Hotfix Context", message)

    def _print_error_log(message: str, print_log: callable = None):
        if print_log:
            print_log("ERROR", "Hotfix Context", "Failed to hotfix context: " + message)

    try:
        context_file: str = os.path.join(get_config_dir(), "context.ttl")

        # Create directory if needed
        if not os.path.exists(os.path.dirname(context_file)):
            os.makedirs(os.path.dirname(context_file), exist_ok=True)
            _print_info_log(f"Created context directory: {os.path.dirname(context_file)}", print_log)

        # Create empty file if needed
        if not os.path.exists(context_file):
            with open(context_file, "w", encoding="utf-8") as f:
                f.write("")
            _print_info_log(f"Created empty context file: {context_file}", print_log)

        graph: Graph = Graph()
        graph.parse(context_file, format="turtle")

        # Ensure required namespaces are bound
        required_namespaces = {
            "rdf": RDF,
            "obdc": OBDC,
            "": BASE_URI,
        }

        for prefix, namespace in required_namespaces.items():
            if prefix not in graph.namespace_manager:
                graph.bind(prefix, namespace)
                _print_info_log(f"Bound namespace '{prefix}' to {namespace}", print_log)

        # Find existing execution context individual
        context_individual: Optional[URIRef] = None
        for s in graph.subjects(predicate=RDF.type, object=OBDC.ExecutionContext):
            context_individual = s
            break

        # Create one if not found
        if not isinstance(context_individual, URIRef):
            context_individual = BASE_URI["CurrentContext"]
            graph.add((context_individual, RDF.type, OWL.NamedIndividual))
            graph.add((context_individual, RDF.type, OBDC.ExecutionContext))
            _print_info_log(f"Created ExecutionContext individual: {context_individual}", print_log)

        # Add config properties
        config_data: ConfigDataPort = ConfigDataAdapter()

        for ns, ns_value in config_data.context_data.items():
            namespace: Optional[Namespace] = get_ontology_by_prefix(ns)
            if isinstance(namespace, Namespace):
                for prop, value in ns_value.items():
                    value = as_literal(value)
                    if value:
                        graph.add((context_individual, namespace[prop], value))

        # Save changes
        graph.serialize(destination=context_file, format="turtle")
        _print_info_log(f"Saved context changes to: {context_file}", print_log)


        return 0
    except Exception as e:
        _print_error_log(f"Error applying hotfix: {e}", print_log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
