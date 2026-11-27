from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.context.plugin.capability.transformation.entity_uri_resolved import (
    EntityUriResolvedCapability,
)
from ontobdc.container.adapter.document_iri import ContainerDocumentIri
from ontobdc.container.adapter.entity_creation import EntityCreation
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.container.adapter.entity_repository import ContainerEntityRepository
from ontobdc.container.adapter.entity_store import ContainerEntityStore
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.context.plugin.machine.action_dates_catalog.state import ActionDatesCatalogProcessState
from ontobdc.container.plugin.machine.entity_write.machine import (
    EntityWriteRequest,
    EntityWriteStateTransitionHandler,
)
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.storage.adapter.crate_file_history import CrateFileHistory
from ontobdc.storage.domain.model.file_history import FileHistory, FileHistoryEntry


class DaysCatalogedCapability(TransactionCapability):
    """
    Creates the day of each date of the timestamps the RO-Crate of the container records for its
    files, when it does not exist, and makes each file a related document of the day of its date.

    The dates are read from the RO-Crate, never from the files. A date is always the UTC date of the
    timestamp, converted to UTC when the timestamp states another offset.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.context.plugin.capability.transformation.target."
            "days_cataloged"
        ),
        version="1.0.0",
        name="Days Cataloged",
        description=(
            "Create the day of each date of the timestamps the RO-Crate records for the files, "
            "and relate each file to the day of its date."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["container", "calendar", "day", "entity", "write"],
        supported_languages=["en", "pt-br"],
        input_schema={"properties": {}},
        output_schema={"properties": {}},
        log_message={
            "info": {"en": "The days of the dates of the files were cataloged."},
            "debug_entry": {"en": "Cataloging the days of the dates of the files."},
        },
    )

    DAY_ENTITY: str = "day"
    DATE_FIELD: str = "date"
    RELATED_FIELD: str = "related_documents"
    SEPARATOR: str = "|"
    CONTAINER_KEY: str = "container_path"

    def label(self, lang: str = "en") -> str:
        return ActionDatesCatalogProcessState.DAYS_CATALOGED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ActionDatesCatalogProcessState.DAYS_CATALOGED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_KEY)
        ).expanduser().resolve()
        ContainerEntityRepository.provide(context)
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)

        day_iri: str = str(EntityUriResolvedCapability.resolve(self.DAY_ENTITY))
        documents: Dict[str, List[str]] = self._documents_by_date(container_path)
        existing: Dict[str, Tuple[str, Set[str]]] = self._existing_days(container_path, repository, day_iri)
        store: ContainerEntityStore = ContainerEntityStore(repository, container_path)

        records: List[Dict[str, Any]] = []
        updated: List[str] = []
        date: str
        for date, iris in sorted(documents.items()):
            if date in existing:
                global_id, related = existing[date]
                if not set(iris) <= related:
                    store.update(global_id, {self.RELATED_FIELD: self.SEPARATOR.join(sorted(related | set(iris)))})
                    updated.append(global_id)
                continue

            records.append(
                EntityCreation.record(
                    EntityFacadeLocator.of(day_iri),
                    {self.DATE_FIELD: date, self.RELATED_FIELD: self.SEPARATOR.join(iris)},
                )
            )

        if records:
            self._write(context, container_path, day_iri, records)

        return {
            "resulting_state": ActionDatesCatalogProcessState.DAYS_CATALOGED,
            "created": [str(record[EntityCreation.IDENTIFIER_FIELD]) for record in records],
            "updated": updated,
        }

    @classmethod
    def _documents_by_date(cls, container_path: Path) -> Dict[str, List[str]]:
        """
        The documents of each date: the files the RO-Crate says are there, by the UTC date of the
        timestamp it records for each, as the IRIs of the documents.
        """
        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(container_path)
        if not crate_file.is_file():
            raise FileNotFoundError(f"The container has no RO-Crate: {crate_file}")

        histories: Dict[str, FileHistory] = CrateFileHistory.read(CrateFileHistory.read_document(crate_file))
        by_date: Dict[str, Set[str]] = {}
        path: str
        history: FileHistory
        for path, history in histories.items():
            entry: Any = history.last_at(path)
            if entry is None or entry.missing_since is not None:
                continue

            date: str = cls._date(entry)
            by_date.setdefault(date, set()).add(
                str(ContainerDocumentIri.of(container_path, container_path / path))
            )

        return {date: sorted(iris) for date, iris in by_date.items()}

    @staticmethod
    def _date(entry: FileHistoryEntry) -> str:
        """
        The date of the timestamp in UTC, whatever offset the timestamp states: a day is always saved
        by its UTC date. A timestamp that states no time zone is an error, never a guess.
        """
        moment: datetime = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError(
                f"The timestamp {entry.timestamp} of {entry.relative_path} states no time zone."
            )

        return moment.astimezone(timezone.utc).date().isoformat()

    @classmethod
    def _existing_days(
        cls,
        container_path: Path,
        repository: EntityRepositoryPort,
        day_iri: str,
    ) -> Dict[str, Tuple[str, Set[str]]]:
        """
        The days the container already keeps, by date: the global id of each and the documents
        related to it.
        """
        days: Dict[str, Tuple[str, Set[str]]] = {}
        dataset: Dict[str, Any]
        for dataset in ContainerEntities.of(container_path):
            if day_iri not in dataset["entity_types"]:
                continue

            dataset_path: Path = container_path / dataset["path"]
            if not repository.data_source_exists(dataset_path):
                continue

            global_id: str
            row: Dict[str, str]
            for global_id, row in repository.rows(dataset_path).items():
                date: str = row.get(cls.DATE_FIELD, "").strip()
                if date and date not in days:
                    related: Set[str] = {
                        iri for iri in row.get(cls.RELATED_FIELD, "").split(cls.SEPARATOR) if iri
                    }
                    days[date] = (global_id, related)

        return days

    @staticmethod
    def _write(context: CliContextPort, container_path: Path, day_iri: str, records: List[Dict[str, Any]]) -> None:
        """
        Writes the new days the way the command that creates an entity does.
        """
        # The path of the container is the one the context already has, and stays: the machine reads it after this.
        keys: List[str] = [
            EntityWriteRequest.ENTITY_IRI_KEY,
            EntityWriteRequest.RECORDS_KEY,
            EntityWriteRequest.SOURCE_DOCUMENTS_KEY,
            EntityWriteRequest.DATASET_PATH_KEY,
        ]
        context.set_parameter_value(EntityWriteRequest.ENTITY_IRI_KEY, day_iri)
        context.set_parameter_value(EntityWriteRequest.RECORDS_KEY, records)
        context.set_parameter_value(EntityWriteRequest.SOURCE_DOCUMENTS_KEY, [])
        try:
            EntityWriteStateTransitionHandler(context).execute()
        finally:
            key: str
            for key in keys:
                context.delete_parameter(key)
