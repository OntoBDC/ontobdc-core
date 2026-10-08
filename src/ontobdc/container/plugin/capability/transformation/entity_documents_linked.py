from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.container.plugin.machine.entity_write.state import EntityWriteProcessState
from ontobdc.container.adapter.entity_linkset import EntityLinkset
from ontobdc.container.domain.port.entity import EntityRepositoryPort


class EntityDocumentsLinkedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.entity_documents_linked",
        version="1.0.0",
        name="Entity Documents Linked",
        description="Write the dataset linkset that ties the data source to the documents the entities were made on.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "entity", "write", "linkset"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The dataset linkset ties the data source to the documents the entities were made on."},
            "debug_entry": {"en": "Writing the linkset of the data source."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Documentos da entidade ligados"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        dataset_path: Path = EntityWriteRequest.dataset_path(context)
        linkset: EntityLinkset = EntityLinkset(
            dataset_path, repository.data_source_path(dataset_path)
        )
        # What an earlier writing linked stays linked: the linkset is the
        # union of the documents of every writing into this data source.
        documents: List[str] = sorted(
            set(linkset.links()) | set(EntityWriteRequest.source_documents(context))
        )
        linkset.write(documents)

        return {
            "resulting_state": EntityWriteProcessState.ENTITY_DOCUMENTS_LINKED,
            "linkset_path": str(linkset.path),
            "documents": documents,
        }
