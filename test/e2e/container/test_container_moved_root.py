import shutil
from typing import Any, Dict, List, Set
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from test.e2e.cli_process_runner import CliInvocationResult, OntobdcCliProcessRunner
from test.e2e.container_workspace import ContainerE2eWorkspace


OBDC_DATA_STORAGE: URIRef = URIRef("http://datacenter.app.br/ontology/tool/ontobdc/core/ns.ttl#DataStorage")


def _locations(graph_file: Path) -> Set[str]:
    graph: Graph = Graph()
    graph.parse(str(graph_file), format="turtle")
    return {str(location) for location in graph.objects(None, PROV.atLocation)}


def _storage_root_location(storage_file: Path) -> str:
    graph: Graph = Graph()
    graph.parse(str(storage_file), format="turtle")
    locations: List[str] = [
        str(location)
        for subject in graph.subjects(RDF.type, OBDC_DATA_STORAGE)
        for location in graph.objects(subject, PROV.atLocation)
    ]
    assert len(locations) == 1, locations
    return locations[0]


class TestOntobdcContainerMovedRoot:
    """
    A storage root is located by its ``.__ontobdc__`` marker, not by the
    absolute paths its graphs recorded when it was created: once the whole
    root is moved (or created elsewhere, e.g. inside a browser's virtual file
    system), its containers keep working from the new place.
    """

    def _moved_workspace(self, tmp_path: Path) -> ContainerE2eWorkspace:
        original_root: Path = tmp_path / "before"
        original_root.mkdir()
        created: ContainerE2eWorkspace = ContainerE2eWorkspace.create(original_root)
        moved_root: Path = tmp_path / "after"
        shutil.move(str(original_root), str(moved_root))
        return ContainerE2eWorkspace(
            root=moved_root.resolve(),
            container=(moved_root / created.container.name).resolve(),
            identifier=created.identifier,
        )

    def test_listing_from_the_moved_root_finds_containers_where_they_are_now(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = self._moved_workspace(tmp_path)

        listing: CliInvocationResult = OntobdcCliProcessRunner(workspace.root).run("container", "--list")

        assert listing.exit_code == 0, listing.stdout + listing.stderr
        containers: List[Dict[str, Any]] = listing.json["content"]["containers"]
        assert [(entry["id"], Path(entry["location"]).resolve()) for entry in containers] == [
            (workspace.identifier, workspace.container)
        ]

    def test_refresh_in_a_moved_container_rewrites_every_location_to_the_new_place(
        self, tmp_path: Path
    ) -> None:
        workspace: ContainerE2eWorkspace = self._moved_workspace(tmp_path)

        result: CliInvocationResult = workspace.runner().run("container", "--refresh")

        assert result.exit_code == 0, result.stdout + result.stderr
        assert result.json["content"]["container_id"] == workspace.identifier
        container_file: Path = workspace.container / ".__ontobdc__" / "container.ttl"
        storage_file: Path = workspace.root / ".__ontobdc__" / "storage.ttl"
        assert _locations(container_file) == {workspace.container.as_uri()}
        assert _locations(storage_file) == {
            workspace.root.as_uri(),
            workspace.container.as_uri(),
        }
        assert _storage_root_location(storage_file) == workspace.root.as_uri()
        assert not (tmp_path / "before").exists()
