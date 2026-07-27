from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import (
    ContainerCreateProcessState,
    DatasetCreateProcessState,
)


class DirectoryReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.directory_ready",
        version="1.0.0",
        name="Directory Ready",
        description="Ensure that the target storage container directory exists.",
        author=["TRAE"],
        tags=["storage", "container", "create"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Directory Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the target directory for the storage container or dataset."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path_value = context.get_parameter_value("container_path")
        resulting_state = ContainerCreateProcessState.DIRECTORY_READY
        if not isinstance(target_path_value, str) or not target_path_value.strip():
            target_path_value = context.get_parameter_value("dataset_path")
            resulting_state = DatasetCreateProcessState.DIRECTORY_READY

        if not isinstance(target_path_value, str) or not target_path_value.strip():
            raise ValueError("Storage target path is missing from the command context.")

        target_path = Path(target_path_value).expanduser().resolve()
        target_path.mkdir(parents=True, exist_ok=True)

        return {
            "resulting_state": resulting_state,
            "path": str(target_path),
            "exists": target_path.exists(),
        }
