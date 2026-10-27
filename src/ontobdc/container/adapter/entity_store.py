from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ontobdc.container.adapter.dataset import RegisteredDatasets
from ontobdc.container.adapter.entity_geometry import EntityGeometries
from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.container.adapter.entity_rules import EntityFieldRules
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.domain.port.entity import EntityRepositoryPort


class ContainerEntityStore:
    """
    The entities a container keeps, found by their global id.

    It looks for the entity in the datasets the container registers whose
    data source the repository can read, and changes or removes its row
    through the repository; where and how rows are kept is the repository's
    business. Only an entity whose dataset has a facade can be changed or
    removed, because the facade says what its fields are.
    """

    def __init__(self, repository: EntityRepositoryPort, container_path: Path) -> None:
        self._repository: EntityRepositoryPort = repository
        self._container_path: Path = container_path

    def locate(self, global_id: str) -> Tuple[Path, Dict[str, str], EntityFacade]:
        """
        The dataset that keeps the entity, its stored row and its facade.

        Raises:
            LookupError: no dataset the repository reads keeps the entity.
            ValueError: the dataset of the entity has no facade.
        """
        dataset_path: Path
        for dataset_path in self._datasets():
            row: Optional[Dict[str, str]] = self._repository.rows(dataset_path).get(global_id)
            if row is None:
                continue

            facade: Optional[EntityFacade] = ContainerEntities.facade_of(dataset_path)
            if facade is None:
                raise ValueError(
                    f"The entity {global_id} is kept by a dataset with no facade, "
                    "so its fields are not known and it cannot be changed."
                )

            return dataset_path, row, facade

        raise LookupError(f"No entity the container keeps has the global id {global_id}.")

    def exists(self, global_id: str) -> bool:
        """
        Whether a dataset the repository reads keeps an entity with this global id.
        """
        dataset_path: Path
        for dataset_path in self._datasets():
            if global_id in self._repository.rows(dataset_path):
                return True

        return False

    def update(self, global_id: str, changes: Dict[str, Any]) -> List[str]:
        """
        Change fields of the entity; returns the fields that changed.

        Raises:
            LookupError, ValueError: as ``locate``, or a field cannot be
                changed or a required field would be left empty.
        """
        dataset_path, row, facade = self.locate(global_id)
        fields: Dict[str, Any] = {field.identifier: field for field in facade.fields}
        changed: Dict[str, str] = {}
        name: str
        value: Any
        for name, value in changes.items():
            field: Any = fields.get(name)
            if field is None or not EntityFieldRules.is_editable(field):
                raise ValueError(f"The field {name} of the entity cannot be changed.")
            if isinstance(value, (dict, list)):
                raise ValueError(f"The field {name} takes a text, not a structure.")

            text: str = "" if value is None else str(value)
            if field.required and not text.strip():
                raise ValueError(f"The field {name} is required.")
            if text != row.get(name, ""):
                changed[name] = text

        if changed:
            # A field the data source has never held (an annotation that was
            # never closed has no completed_at) gets its column when first written.
            missing: List[str] = [name for name in changed if name not in row]
            if missing:
                self._repository.add_columns(dataset_path, missing)
            self._repository.upsert_rows(dataset_path, [{**row, **changed}])

        return sorted(changed)

    def delete(self, global_id: str) -> None:
        """
        Remove the entity. Raises as ``locate`` does.
        """
        dataset_path, _, _ = self.locate(global_id)
        self._repository.delete_rows(dataset_path, [global_id])
        EntityGeometries.delete(dataset_path, global_id)

    def _datasets(self) -> List[Path]:
        return [
            dataset_path
            for dataset_path in ContainerEntities.distinct_datasets(self._container_path)
            if self._repository.data_source_exists(dataset_path)
        ]
