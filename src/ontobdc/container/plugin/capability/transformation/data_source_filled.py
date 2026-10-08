from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.container.plugin.machine.entity_write.state import EntityWriteProcessState
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.domain.port.entity import EntityRepositoryPort


class DataSourceFilledCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.data_source_filled",
        version="1.0.0",
        name="Data Source Filled",
        description="Write the rows of the entities into the data source, after checking them against the entity facade.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "entity", "write"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The data source holds the rows of the entities."},
            "debug_entry": {"en": "Writing the rows of the entities into the data source."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Fonte de dados preenchida"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        dataset_path: Path = EntityWriteRequest.dataset_path(context)
        facade: EntityFacade = EntityFacadeLocator.of(
            EntityWriteRequest.entity_iri(context)
        )
        records: List[Dict[str, Any]] = EntityWriteRequest.records(context)

        record: Dict[str, Any]
        for record in records:
            self._validate(facade, record)
        repository.upsert_rows(dataset_path, records)

        return {
            "resulting_state": EntityWriteProcessState.DATA_SOURCE_FILLED,
            "rows": len(records),
        }

    @staticmethod
    def _validate(facade: EntityFacade, record: Dict[str, Any]) -> None:
        undeclared: List[str] = [
            key for key in record if facade.field(key) is None
        ]
        if undeclared:
            raise ValueError(
                f"The row {record.get('global_id')!r} has fields the facade of "
                f"<{facade.entity_iri}> does not declare: {undeclared}."
            )

        missing: List[str] = [
            declared.identifier
            for declared in facade.fields
            if declared.required
            and (record.get(declared.identifier) is None
                 or not str(record.get(declared.identifier)).strip())
        ]
        if missing:
            raise ValueError(
                f"The row {record.get('global_id')!r} lacks the required "
                f"fields: {missing}."
            )
