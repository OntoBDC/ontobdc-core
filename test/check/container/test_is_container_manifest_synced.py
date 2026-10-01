import json
from typing import Any, Dict, List, Set

from test.check.container.container_workspace import ContainerCheckWorkspace
from ontobdc.container.plugin.check.is_container_metadata_ready import hotfix as metadata_hotfix
from ontobdc.container.plugin.check.is_container_manifest_synced import check, hotfix
from ontobdc.container.plugin.check.is_container_storage_index_ready import hotfix as index_hotfix


class TestIsContainerManifestSynced:
    """
    Standalone coverage for the `is_container_manifest_synced` check and its
    hotfix, which keep the RO-Crate manifest of a container aligned with the
    files actually present on disk.
    """

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def _prepare_indexed_container(self) -> None:
        assert metadata_hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert index_hotfix.main(self.workspace.container, self.workspace.root) == 0

    def _manifest_file_ids(self) -> Set[str]:
        manifest: Dict[str, Any] = json.loads(
            self.workspace.crate_metadata_file.read_text(encoding="utf-8"),
        )
        entities: List[Dict[str, Any]] = manifest["@graph"]
        root_entities: List[Dict[str, Any]] = [
            entity for entity in entities if entity.get("@id") == "./"
        ]
        assert len(root_entities) == 1

        return {part["@id"] for part in root_entities[0]["hasPart"]}

    def test_check_fails_on_a_bare_container(self) -> None:
        assert check.main(self.workspace.container, self.workspace.root) == 1

    def test_check_fails_without_arguments(self) -> None:
        assert check.main() == 1
        assert check.main(self.workspace.container, "") == 1

    def test_hotfix_fails_while_the_storage_index_is_missing(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 1
        assert not self.workspace.crate_metadata_file.exists()

    def test_hotfix_writes_the_crate_manifest(self) -> None:
        self._prepare_indexed_container()
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self.workspace.crate_metadata_file.is_file()
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_manifest_lists_the_container_dataset_files(self) -> None:
        self._prepare_indexed_container()
        self.workspace.add_dataset("dataset-one")
        self.workspace.add_file("dataset-one/table.csv", "a,b\n1,2\n")

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0
        assert self._manifest_file_ids() == {
            "dataset-one/dataset.ttl",
            "dataset-one/table.csv",
        }

    def test_check_detects_a_file_added_after_the_last_sync(self) -> None:
        self._prepare_indexed_container()
        self.workspace.add_dataset("dataset-one")
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        self.workspace.add_file("dataset-one/table.csv", "a,b\n1,2\n")
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0
        assert "dataset-one/table.csv" in self._manifest_file_ids()

    def test_check_detects_a_file_removed_after_the_last_sync(self) -> None:
        self._prepare_indexed_container()
        self.workspace.add_dataset("dataset-one")
        self.workspace.add_file("dataset-one/table.csv", "a,b\n1,2\n")
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        (self.workspace.container_path / "dataset-one" / "table.csv").unlink()
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self._manifest_file_ids() == {"dataset-one/dataset.ttl"}

    def test_check_fails_when_the_manifest_is_unreadable(self) -> None:
        self._prepare_indexed_container()
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0

        self.workspace.crate_metadata_file.write_text("{ not json", encoding="utf-8")
        assert check.main(self.workspace.container, self.workspace.root) == 1

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_hotfix_is_idempotent(self) -> None:
        self._prepare_indexed_container()
        self.workspace.add_dataset("dataset-one")
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        first_manifest: str = self.workspace.crate_metadata_file.read_text(encoding="utf-8")

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self._manifest_file_ids() == {"dataset-one/dataset.ttl"}
        assert check.main(self.workspace.container, self.workspace.root) == 0
        assert json.loads(first_manifest)["@graph"][0]["@id"] == "./"
