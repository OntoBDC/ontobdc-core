from pathlib import Path
from typing import List, Set

from rdflib import URIRef
from rdflib.graph import Graph
from rdflib.namespace import OWL, Namespace

from brasidatacenter import resources
from brasidatacenter.tool.adapter import ontology_cache

from ontobdc.shared.domain.port.ontology import OntologyLibraryPort


class BrasidataCenterOntologyLibrary(OntologyLibraryPort):
    """
    The ontologies shipped by the installed ``brasidatacenter`` package.

    The package publishes each ontology at the IRI that names its file
    (``ONTOLOGY_BASE_IRI`` followed by the file's path under ``ontology/``),
    so an ontology is found from its IRI alone. An IRI the package has no
    file for is an error, never a reason to look elsewhere.
    """

    def path(self, iri: str) -> Path:
        try:
            return Path(str(resources.ontology_path_for_iri(iri)))
        except ValueError as error:
            raise FileNotFoundError(str(error)) from error

    def graph(self, iri: str) -> Graph:
        """
        The graph of the ontology, parsed once per process and shared: it must only be read. Parsing
        the same files again for every question was most of the time a command took. To change one,
        take a copy (``graph_copy``).
        """
        return ontology_cache.parsed(self.path(iri))

    def graph_copy(self, iri: str) -> Graph:
        """A graph with what the ontology says, which the caller may change."""
        return ontology_cache.copy(self.path(iri))

    def graph_with_imports(self, iri: str) -> Graph:
        merged: Graph = Graph()
        loaded: Set[str] = set()
        pending: List[str] = [self._ontology_iri(iri)]
        while pending:
            ontology_iri: str = pending.pop()
            if ontology_iri in loaded:
                continue
            loaded.add(ontology_iri)

            ontology: Graph = self.graph(ontology_iri)
            for prefix, namespace in ontology.namespaces():
                merged.bind(prefix, namespace, override=False)
            merged += ontology
            pending.extend(
                str(imported)
                for imported in ontology.objects(URIRef(ontology_iri), OWL.imports)
            )

        return merged

    def iris(self) -> List[str]:
        root: Path = Path(str(resources.ontology_root()))
        return sorted(
            resources.ONTOLOGY_BASE_IRI + Path(str(ontology_file)).relative_to(root).as_posix()
            for ontology_file in resources.iter_ontology_files()
        )

    @staticmethod
    def bound_namespace(graph: Graph, prefix: str) -> Namespace:
        """
        The namespace the ontology in ``graph`` binds to ``prefix``.

        Raises:
            LookupError: the ontology binds nothing to ``prefix``.
        """
        bound_prefix: str
        namespace: URIRef
        for bound_prefix, namespace in graph.namespaces():
            if bound_prefix == prefix:
                return Namespace(str(namespace))
        raise LookupError(f"The ontology binds no namespace to the prefix '{prefix}'.")

    @staticmethod
    def _ontology_iri(iri: str) -> str:
        """
        The IRI of the ontology itself, without a term fragment.
        """
        return iri.split("#", 1)[0]
