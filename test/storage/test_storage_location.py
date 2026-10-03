from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF

from ontobdc.storage.domain.model.graph import StorageGraphModel
from ontobdc.storage.domain.exception.location import InconsistentStorageIndexError
from ontobdc.storage.domain.model.location import StorageLocation


OBDC: Namespace = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")


class TestStorageLocation:
    """
    Locations recorded in a storage index are read relative to where the
    storage root is now, not to where it was when they were recorded.
    """

    def test_a_location_under_the_recorded_root_follows_the_root(self) -> None:
        assert StorageLocation.rebase(
            Path("/old/root/projects/a"), Path("/old/root"), Path("/new/place")
        ) == Path("/new/place/projects/a")

    def test_a_location_outside_the_recorded_root_is_an_inconsistent_index(self) -> None:
        with pytest.raises(InconsistentStorageIndexError):
            StorageLocation.rebase(Path("/mnt/attached"), Path("/old/root"), Path("/new/place"))

    def test_an_index_whose_root_recorded_no_location_is_read_as_recorded(self) -> None:
        assert StorageLocation.rebase(Path("/old/root/a"), None, Path("/new")) == Path("/old/root/a")

    def test_file_uris_and_plain_paths_are_read_alike(self) -> None:
        assert StorageLocation.to_path("file:///old/root/a%20b") == Path("/old/root/a b").resolve()
        assert StorageLocation.to_path("/old/root/a b") == Path("/old/root/a b").resolve()

    def test_the_storage_model_lists_containers_where_they_are_now(self) -> None:
        graph: Graph = Graph()
        storage: URIRef = URIRef("urn:ontobdc:storage/local")
        graph.add((storage, RDF.type, OBDC.DataStorage))
        graph.add((storage, PROV.atLocation, URIRef("file:///storage/raiz")))
        container: URIRef = URIRef("urn:uuid:00000000-0000-4000-8000-000000000001")
        graph.add((container, RDF.type, OBDC.DataContainer))
        graph.add((container, DCTERMS.identifier, URIRef(str(container))))
        graph.add((container, PROV.atLocation, URIRef("file:///storage/raiz/meu-projeto")))

        model: StorageGraphModel = StorageGraphModel(graph, root_path=Path("/home/elias/raiz"))

        assert [entry["location"] for entry in model.list_containers()] == [
            str(Path("/home/elias/raiz/meu-projeto"))
        ]
