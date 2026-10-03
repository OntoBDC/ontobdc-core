from typing import Optional
from pathlib import Path

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import PROV, RDF

from test.check.container.container_workspace import ContainerCheckWorkspace
from ontobdc.container.plugin.check.is_container_metadata_ready import hotfix as metadata_hotfix
from ontobdc.container.plugin.check.is_container_storage_index_ready import check, hotfix
from ontobdc.storage.domain.exception.location import InconsistentStorageIndexError

OBDC: Namespace = Namespace("http://ontobdc.org/ontology/domain/ontobdc/ns.ttl#")


class TestIsContainerStorageIndexReady:
    """
    Standalone coverage for the `is_container_storage_index_ready` check and
    its hotfix, including the dependency on the container metadata check that
    both scripts evaluate before touching the root storage index.
    """

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_check_fails_on_a_bare_container(self) -> None:
        assert check.main(self.workspace.container, self.workspace.root) == 1

    def test_check_fails_without_arguments(self) -> None:
        assert check.main() == 1
        assert check.main(self.workspace.container, "") == 1

    def test_hotfix_fails_while_the_container_metadata_is_missing(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 1
        assert not self.workspace.root_storage_file.exists()

    def test_hotfix_indexes_the_container_in_the_root_storage(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self.workspace.root_storage_file.is_file()
        assert check.main(self.workspace.container, self.workspace.root) == 0

        identifier: Optional[str] = self.workspace.read_container_identifier()
        assert identifier is not None
        assert identifier in self.workspace.root_storage_file.read_text(encoding="utf-8")

    def test_hotfix_is_idempotent(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        indexed_storage: str = self.workspace.root_storage_file.read_text(encoding="utf-8")

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self.workspace.root_storage_file.read_text(encoding="utf-8") == indexed_storage
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_check_fails_when_the_root_storage_index_is_deleted(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        self.workspace.root_storage_file.unlink()
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_check_fails_when_the_root_storage_index_is_unparseable(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        self.workspace.root_storage_file.write_text("<<< not turtle", encoding="utf-8")
        assert check.main(self.workspace.container, self.workspace.root) == 1

    def test_check_fails_when_the_container_metadata_is_invalidated(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        self.workspace.replace_container_identifier("urn:uuid:not-a-valid-identifier")
        assert check.main(self.workspace.container, self.workspace.root) == 1

    def _write_index_recorded_at(self, old_root: Path, *container_locations: Path) -> None:
        """Write a storage index as if the root had been recorded at ``old_root``."""
        storage: Graph = Graph()
        storage_subject: URIRef = URIRef("urn:ontobdc:storage/local")
        storage.add((storage_subject, RDF.type, OBDC.DataStorage))
        storage.add((storage_subject, PROV.atLocation, URIRef(old_root.as_uri())))
        for index, location in enumerate(container_locations, start=1):
            subject: URIRef = URIRef(f"urn:uuid:00000000-0000-4000-8000-{index:012d}")
            storage.add((subject, RDF.type, OBDC.DataContainer))
            storage.add((subject, PROV.atLocation, URIRef(location.as_uri())))
        self.workspace.root_storage_file.parent.mkdir(parents=True, exist_ok=True)
        storage.serialize(destination=str(self.workspace.root_storage_file), format="turtle")

    def test_hotfix_writes_the_index_for_the_root_current_place(self) -> None:
        """
        An index recorded somewhere else (the root was moved, or created in
        another file system) is rewritten for where the root is now: its own
        location and every location recorded under it.
        """
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        old_root: Path = Path("/elsewhere/old-root")
        self._write_index_recorded_at(old_root, old_root / "sibling")
        storage_subject: URIRef = URIRef("urn:ontobdc:storage/local")
        sibling: URIRef = URIRef("urn:uuid:00000000-0000-4000-8000-000000000001")

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        written: Graph = Graph()
        written.parse(str(self.workspace.root_storage_file), format="turtle")
        assert list(written.objects(storage_subject, PROV.atLocation)) == [
            URIRef(self.workspace.root_path.as_uri())
        ]
        assert list(written.objects(sibling, PROV.atLocation)) == [
            URIRef((self.workspace.root_path / "sibling").as_uri())
        ]
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_hotfix_refuses_an_index_with_a_location_outside_its_root(self) -> None:
        """Every container lives under its root: an index saying otherwise is inconsistent."""
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        self._write_index_recorded_at(Path("/elsewhere/old-root"), Path("/mnt/attached/container"))
        recorded: bytes = self.workspace.root_storage_file.read_bytes()

        with pytest.raises(InconsistentStorageIndexError):
            hotfix.main(self.workspace.container, self.workspace.root)
        assert self.workspace.root_storage_file.read_bytes() == recorded
