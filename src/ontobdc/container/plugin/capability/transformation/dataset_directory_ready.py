from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.dataset_create.state import DatasetCreateProcessState


class DatasetDirectoryReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.dataset_directory_ready",
        version="1.0.0",
        name="Dataset Directory Ready",
        description="Ensure that the target storage dataset directory exists.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "create"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": "The dataset directory exists and is ready for downstream steps.",
            },
            "debug_entry": {
                "en": "Preparing the dataset directory for downstream steps.",
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Dataset Directory Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the target directory of the storage dataset."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path_value: Any = context.get_parameter_value("dataset_path")
        if not isinstance(target_path_value, str) or not target_path_value.strip():
            raise ValueError("Storage dataset path is missing from the command context.")

        target_path: Path = Path(target_path_value).expanduser().resolve()
        target_path.mkdir(parents=True, exist_ok=True)

        return {
            "resulting_state": DatasetCreateProcessState.DIRECTORY_READY,
            "path": str(target_path),
            "exists": target_path.exists(),
        }
