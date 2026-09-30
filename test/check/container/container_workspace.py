import re
import shutil
from typing import ClassVar, List, Optional, Pattern
from pathlib import Path
import tempfile

from ontobdc.storage.adapter.bootstrap import StorageBootstrap, StorageLayoutConstants


class ContainerCheckWorkspace:
    """
    Disposable on-disk workspace used by the container check/hotfix suites.

    A workspace owns a temporary storage root plus a single container
    directory inside it, which is the exact pair of paths every
    `check.main(container_path, root_path)` and `hotfix.main(...)` entry
    point expects. Nothing is pre-populated: the scripts under test are
    the ones responsible for creating `.__ontobdc__` and its files.
    """

    ROOT_PREFIX: ClassVar[str] = "ontobdc-check-"
    CONTAINER_DIRECTORY_NAME: ClassVar[str] = "container-under-test"
    IDENTIFIER_PATTERN: ClassVar[Pattern[str]] = re.compile(r"urn:uuid:[0-9a-fA-F-]{36}")

    def __init__(self) -> None:
        self._root_path: Path = Path(tempfile.mkdtemp(prefix=self.ROOT_PREFIX)).resolve()
        self._container_path: Path = self._root_path / self.CONTAINER_DIRECTORY_NAME
        self._container_path.mkdir()

    @property
    def root_path(self) -> Path:
        return self._root_path

    @property
    def container_path(self) -> Path:
        return self._container_path

    @property
    def root(self) -> str:
        return str(self._root_path)

    @property
    def container(self) -> str:
        return str(self._container_path)

    @property
    def container_storage_file(self) -> Path:
        return StorageBootstrap.get_container_storage_file_path(self._container_path)

    @property
    def root_storage_file(self) -> Path:
        return StorageBootstrap.get_storage_file_path(self._root_path)

    @property
    def crate_metadata_file(self) -> Path:
        return StorageBootstrap.get_container_crate_metadata_file_path(self._container_path)

    def add_dataset(self, dataset_name: str) -> Path:
        dataset_path: Path = self._container_path / dataset_name
        dataset_path.mkdir(parents=True, exist_ok=True)
        marker_path: Path = dataset_path / StorageLayoutConstants.DATASET_STORAGE_FILE_NAME
        marker_path.write_text("", encoding="utf-8")
        return dataset_path

    def add_file(self, relative_path: str, content: str) -> Path:
        file_path: Path = self._container_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def read_container_identifier(self) -> Optional[str]:
        if not self.container_storage_file.is_file():
            return None

        identifiers: List[str] = self.IDENTIFIER_PATTERN.findall(
            self.container_storage_file.read_text(encoding="utf-8"),
        )
        if not identifiers:
            return None

        return identifiers[0]

    def replace_container_identifier(self, replacement: str) -> None:
        identifier: Optional[str] = self.read_container_identifier()
        if identifier is None:
            return

        content: str = self.container_storage_file.read_text(encoding="utf-8")
        self.container_storage_file.write_text(
            content.replace(identifier, replacement),
            encoding="utf-8",
        )

    def dispose(self) -> None:
        shutil.rmtree(self._root_path, ignore_errors=True)
