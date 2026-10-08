from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.entity_write.machine import EntityWriteRequest
from ontobdc.container.plugin.machine.entity_write.state import EntityWriteProcessState
from ontobdc.shared.adapter.slug import TitleSlug
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.plugin.check.is_dataset_structure_valid.hotfix import (
    main as make_dataset_structure,
)
from ontobdc.container.plugin.machine.dataset_create.machine import (
    DatasetCreateStateTransitionHandler,
)


class DatasetFoundCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.dataset_found",
        version="1.0.0",
        name="Dataset Found",
        description="Find the container dataset that holds the entity or, when it has none, create it.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "entity", "write"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {"en": "The container has a dataset that holds the entity."},
            "debug_entry": {"en": "Looking for the container dataset that holds the entity."},
        },
    )

    def label(self, lang: str = "en") -> str:
        if lang.lower() == "pt-br":
            return "Dataset encontrado"
        return self.metadata.name

    def description(self, lang: str = "en") -> str:
        return self.metadata.description

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        The first dataset of the container that holds the entity is the one
        used. When there is none, one is created for the entity, named after
        its facade.
        """
        container_path: Path = EntityWriteRequest.container_path(context)
        entity_iri: str = EntityWriteRequest.entity_iri(context)
        facade: EntityFacade = EntityFacadeLocator.of(entity_iri)

        dataset_path: Path = container_path / TitleSlug.of(facade.name)
        if dataset_path.exists():
            raise FileExistsError(
                f"{dataset_path} exists but is not a dataset that holds <{entity_iri}>."
            )

        context.set_parameter_value(EntityWriteRequest.DATASET_PATH_KEY, str(dataset_path))
        context.set_parameter_value("dataset_title", facade.name)
        DatasetCreateStateTransitionHandler(context).execute()
        if make_dataset_structure(dataset_path=str(dataset_path)) != 0:
            raise RuntimeError(
                f"Failed to make the structure of the dataset at {dataset_path}."
            )

        return {
            "resulting_state": EntityWriteProcessState.DATASET_FOUND,
            "dataset_path": str(dataset_path),
            "created": True,
        }
