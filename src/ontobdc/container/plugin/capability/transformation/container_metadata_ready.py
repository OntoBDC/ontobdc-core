from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_create.state import ContainerCreateProcessState
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata_ready,
)


class ContainerMetadataReadyCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.container_metadata_ready",
        version="1.0.0",
        name="Container Metadata Ready",
        description="Ensure that the target storage container metadata file exists with valid container metadata.",
        author=["TRAE"],
        tags=["storage", "container", "create", "metadata"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container metadata preparation finished, and the metadata file "
                    "is valid and ready for downstream steps."
                ),
            },
            "debug_entry": {
                "en": (
                    "Preparing and validating the container metadata file "
                    "for downstream steps."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerCreateProcessState.CONTAINER_METADATA_READY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerCreateProcessState.CONTAINER_METADATA_READY.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        container_path_str: str = str(container_path)
        root_path: str = str(context.root_path).strip()
        container_title_value: Any = context.get_parameter_value("container_title")
        container_title: Optional[str] = None
        if container_title_value is not None:
            if (
                not isinstance(container_title_value, str)
                or not container_title_value.strip()
            ):
                raise ValueError(
                    "The container title must be a non-empty string."
                )
            container_title = container_title_value.strip()

        metadata_ready: bool = check_container_metadata_ready(
            container_path=container_path_str,
            root_path=root_path,
        ) == 0
        if not metadata_ready or container_title is not None:
            if hotfix_container_metadata_ready(
                container_path=container_path_str,
                root_path=root_path,
                container_title=container_title,
            ) != 0:
                raise ValueError("Failed to hotfix container metadata during storage container creation.")

        if check_container_metadata_ready(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            raise ValueError("Container metadata is still invalid after the storage container hotfix.")

        return {
            "resulting_state": ContainerCreateProcessState.CONTAINER_METADATA_READY,
            "container_path": container_path_str,
        }
