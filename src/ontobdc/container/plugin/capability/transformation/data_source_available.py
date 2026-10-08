from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.container.plugin.machine.entity_write.state import EntityWriteProcessState
from ontobdc.container.domain.port.entity import EntityRepositoryPort


class DataSourceAvailableCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.data_source_available",
        version="1.0.0",
        name="Data Source Available",
        description="Ask the repository for the data source of the dataset and have it created when it is not there.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "entity", "write"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The dataset has the data source of the entity."},
            "debug_entry": {"en": "Making the data source of the entity available in the dataset."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Fonte de dados disponível"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        dataset_path: Path = EntityWriteRequest.dataset_path(context)
        if not repository.data_source_exists(dataset_path):
            repository.create_data_source(dataset_path)

        return {
            "resulting_state": EntityWriteProcessState.DATA_SOURCE_AVAILABLE,
            "data_source_path": str(repository.data_source_path(dataset_path)),
        }
