import zipfile
from pathlib import Path
from typing import ClassVar

from rdflib import Graph

from ontobdc.storage.domain.exception.obdc import StorageObdcFileError
from ontobdc.storage.domain.model.obdc import StorageObdcRemoteModel
from ontobdc.storage.domain.port.obdc import (
    StorageObdcRemoteModelPort,
    StorageObdcRepositoryPort,
)


class StorageObdcRepository(StorageObdcRepositoryPort):
    """
    Reads ``.obdc`` files: zip archives that carry an ``remote.ttl``.
    """

    REMOTE_NAME: ClassVar[str] = "remote.ttl"
    REMOTE_FORMAT: ClassVar[str] = "turtle"

    def read_remote(self, obdc_path: Path) -> StorageObdcRemoteModelPort:
        try:
            with zipfile.ZipFile(obdc_path) as archive:
                content: bytes = archive.read(self.REMOTE_NAME)
        except FileNotFoundError:
            raise StorageObdcFileError(f"The .obdc file does not exist: {obdc_path}") from None
        except zipfile.BadZipFile:
            raise StorageObdcFileError(f"The .obdc file is not a zip archive: {obdc_path}") from None
        except KeyError:
            raise StorageObdcFileError(
                f"The .obdc file holds no {self.REMOTE_NAME}: {obdc_path}"
            ) from None

        graph: Graph = Graph()
        try:
            graph.parse(data=content, format=self.REMOTE_FORMAT)
        except Exception as error:
            raise StorageObdcFileError(
                f"The {self.REMOTE_NAME} of the .obdc file is not valid Turtle: {obdc_path}"
            ) from error

        return StorageObdcRemoteModel(graph)
