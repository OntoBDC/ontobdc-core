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


class DataSourceColumnsSyncedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.data_source_columns_synced",
        version="1.0.0",
        name="Data Source Columns Synced",
        description="Add to the data source the columns of the entity facade that it does not have yet.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "entity", "write"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The data source has a column for every field of the entity facade."},
            "debug_entry": {"en": "Adding the missing facade columns to the data source."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Colunas da fonte de dados sincronizadas"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        dataset_path: Path = EntityWriteRequest.dataset_path(context)
        facade: EntityFacade = EntityFacadeLocator.of(
            EntityWriteRequest.entity_iri(context)
        )

        present: List[str] = repository.columns(dataset_path)
        missing: List[str] = [
            column for column in facade.column_names() if column not in present
        ]
        if missing:
            repository.add_columns(dataset_path, missing)

        return {
            "resulting_state": EntityWriteProcessState.DATA_SOURCE_COLUMNS_SYNCED,
            "added_columns": missing,
        }
