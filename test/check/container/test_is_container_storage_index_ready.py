from typing import Optional

from test.check.container.container_workspace import ContainerCheckWorkspace
from ontobdc.container.plugin.check.is_container_metadata_ready import hotfix as metadata_hotfix
from ontobdc.container.plugin.check.is_container_storage_index_ready import check, hotfix


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
