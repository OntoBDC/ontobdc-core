from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import DatasetCreateProcessState
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.storage.plugin.check.is_dataset_metadata_ready.hotfix import (
    main as hotfix_dataset_metadata_ready,
)


class DatasetMetadataReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.dataset_metadata_ready",
        version="1.0.0",
        name="Dataset Metadata Ready",
        description="Ensure that the target storage dataset metadata file exists with valid dataset metadata.",
        author=["TRAE"],
        tags=["storage", "dataset", "create", "metadata"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Dataset Metadata Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the local dataset metadata file without requiring linkset or payload relations."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("dataset_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_dataset_metadata_ready(
            dataset_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_dataset_metadata_ready(
                dataset_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix dataset metadata during storage dataset creation.")

        if check_dataset_metadata_ready(
            dataset_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("Dataset metadata is still invalid after the storage dataset hotfix.")

        return {
            "resulting_state": DatasetCreateProcessState.DATASET_METADATA_READY,
            "path": target_path,
        }
