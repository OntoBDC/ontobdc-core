from pathlib import Path
from typing import Dict, Optional

from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.adapter.entity_geometry import EntityGeometries
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.annotate.domain.model.annotate import Annotation
from ontobdc.annotate.domain.model.view import AnnotationView


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

    def annotation(self, guid: str) -> Annotation:
        """
        The annotation, with the geometries that are kept beside its row. Raises as ``row`` does.
        """
        stored: Dict[str, str] = self.row(guid)
        return Annotation.from_record(stored, EntityGeometries.read(self._dataset_path(), guid))

    def delete(self, guid: str) -> None:
        """
        Remove the annotation, and its geometries and view. Raises ``LookupError`` as ``row`` does.
        """
        self.row(guid)
        dataset_path: Path = self._dataset_path()
        self._repository.delete_rows(dataset_path, [guid])
        EntityGeometries.delete(dataset_path, guid)
        self.view_path(guid).unlink(missing_ok=True)

    def view_path(self, guid: str) -> Path:
        """
        Where the view of the annotation is kept: in the documents of the dataset, named by the global id of the annotation.
        """
        return self._dataset_path() / "payload" / "document" / AnnotationView.file_name(guid)

    def _dataset_path(self) -> Path:
        dataset_path: Optional[Path] = EntityDatasets.first(
            self._container_path, Annotation.ENTITY_IRI
        )
        if dataset_path is None or not self._repository.data_source_exists(dataset_path):
            raise LookupError(f"The container {self._container_path} keeps no annotations.")

        return dataset_path
