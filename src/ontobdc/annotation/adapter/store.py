from pathlib import Path
from typing import Dict, Optional

from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.annotation.domain.model.annotation import Annotation


class AnnotationStore:
    """
    The annotations a container keeps, found by their global id.

    It knows which dataset of the container holds the annotations and asks the
    entity repository for the rows; where and how the rows are kept is the
    repository's business.
    """

    def __init__(self, repository: EntityRepositoryPort, container_path: Path) -> None:
        self._repository: EntityRepositoryPort = repository
        self._container_path: Path = container_path

    def row(self, guid: str) -> Dict[str, str]:
        """
        The stored row of the annotation.

        Raises:
            LookupError: the container keeps no annotations, or none with
                this global id.
        """
        dataset_path: Path = self._dataset_path()
        stored: Optional[Dict[str, str]] = self._repository.rows(dataset_path).get(guid)
        if stored is None:
            raise LookupError(f"No annotation has the global id {guid}.")

        return stored

    def delete(self, guid: str) -> None:
        """
        Remove the annotation. Raises ``LookupError`` as ``row`` does.
        """
        self.row(guid)
        self._repository.delete_rows(self._dataset_path(), [guid])

    def _dataset_path(self) -> Path:
        dataset_path: Optional[Path] = EntityDatasets.first(
            self._container_path, Annotation.ENTITY_IRI
        )
        if dataset_path is None or not self._repository.data_source_exists(dataset_path):
            raise LookupError(f"The container {self._container_path} keeps no annotations.")

        return dataset_path
