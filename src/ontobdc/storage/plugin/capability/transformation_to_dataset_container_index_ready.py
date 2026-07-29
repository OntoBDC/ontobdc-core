
from typing import Any, Dict
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import DatasetCreateProcessState
from ontobdc.storage.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)
from ontobdc.storage.plugin.check.is_dataset_container_index_ready.hotfix import (
    main as hotfix_dataset_container_index_ready,
)


class DatasetContainerIndexReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.dataset_container_index_ready",
        version="1.0.0",
        name="Dataset Container Index Ready",
        description="Ensure that container.ttl is synchronized with the dataset metadata file for the target dataset.",
        author=["TRAE"],
        tags=["storage", "dataset", "create", "index"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Dataset Container Index Ready"

    def description(self, lang: str = "en") -> str:
        return "Synchronizes the dataset entry inside container.ttl with the dataset.ttl metadata."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("dataset_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_dataset_container_index_ready(
            dataset_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_dataset_container_index_ready(
                dataset_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix dataset container index entry during storage dataset creation.")

        if check_dataset_container_index_ready(
            dataset_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("Dataset container index entry is still invalid after the storage dataset hotfix.")

        return {
            "resulting_state": DatasetCreateProcessState.DATASET_CONTAINER_INDEX_READY,
            "path": target_path,
        }
