from typing import Optional
from pathlib import Path

from ontobdc.storage.adapter.identifier import ContainerIdentifier
from test.check.container.container_workspace import ContainerCheckWorkspace
from ontobdc.container.plugin.check.is_container_metadata_ready import check, hotfix


class TestIsContainerMetadataReady:
    """
    Standalone coverage for the `is_container_metadata_ready` check and its
    hotfix: both are plain scripts, so they are exercised through their
    `main(container_path, root_path) -> int` entry points only.
    """

    def setup_method(self) -> None:
        self.workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()

    def teardown_method(self) -> None:
        self.workspace.dispose()

    def test_check_fails_on_a_bare_container(self) -> None:
        assert check.main(self.workspace.container, self.workspace.root) == 1
        assert not self.workspace.container_storage_file.exists()

    def test_check_fails_without_arguments(self) -> None:
        assert check.main() == 1
        assert check.main(self.workspace.container, "   ") == 1
        assert check.main("", self.workspace.root) == 1

    def test_check_fails_for_a_container_that_is_not_a_directory(self) -> None:
        missing_container: Path = self.workspace.container_path / "absent"

        assert check.main(str(missing_container), self.workspace.root) == 1

    def test_check_fails_for_a_container_outside_the_root(self) -> None:
        outside_workspace: ContainerCheckWorkspace = ContainerCheckWorkspace()
        try:
            assert hotfix.main(outside_workspace.container, outside_workspace.root) == 0
            assert check.main(outside_workspace.container, self.workspace.root) == 1
        finally:
            outside_workspace.dispose()

    def test_hotfix_makes_the_check_pass(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0

        identifier: Optional[str] = self.workspace.read_container_identifier()
        assert identifier is not None
        assert ContainerIdentifier.is_valid(identifier)

    def test_hotfix_is_idempotent_and_preserves_the_identifier(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        first_identifier: Optional[str] = self.workspace.read_container_identifier()

        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert self.workspace.read_container_identifier() == first_identifier
        assert check.main(self.workspace.container, self.workspace.root) == 0

    def test_check_rejects_an_invalid_identifier(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        self.workspace.replace_container_identifier("urn:uuid:not-a-valid-identifier")

        assert check.main(self.workspace.container, self.workspace.root) == 1

    def test_check_rejects_unparseable_container_metadata(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        self.workspace.container_storage_file.write_text("<<< not turtle", encoding="utf-8")

        assert check.main(self.workspace.container, self.workspace.root) == 1

    def test_hotfix_recovers_a_deleted_container_metadata_file(self) -> None:
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        self.workspace.container_storage_file.unlink()

        assert check.main(self.workspace.container, self.workspace.root) == 1
        assert hotfix.main(self.workspace.container, self.workspace.root) == 0
        assert check.main(self.workspace.container, self.workspace.root) == 0
