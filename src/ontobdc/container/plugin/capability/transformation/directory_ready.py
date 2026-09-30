from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_create.state import ContainerCreateProcessState


class DirectoryReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.directory_ready",
        version="1.0.0",
        name="Directory Ready",
        description="Ensure that the target storage container directory exists.",
        author=["TRAE"],
        tags=["storage", "container", "create"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container directory preparation finished, and the target "
                    "directory is ready for downstream steps."
                ),
            },
            "debug_entry": {
                "en": (
                    "Preparing the container directory for downstream "
                    "steps."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Directory Ready"

    def description(self, lang: str = "en") -> str:
        return "Creates the target directory for the storage container or dataset."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Create the target container directory.
        """
        target_path_value: Any = context.get_parameter_value("container_path")
        if not isinstance(target_path_value, str) or not target_path_value.strip():
            raise ValueError("Storage target path is missing from the command context.")

        target_path: Path = Path(target_path_value).expanduser().resolve()
        target_path.mkdir(parents=True, exist_ok=True)

        return {
            "resulting_state": ContainerCreateProcessState.DIRECTORY_READY,
            "path": str(target_path),
            "exists": target_path.exists(),
        }
