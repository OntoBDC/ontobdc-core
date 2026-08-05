from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import (
    CapabilityExecutor,
    TransactionCapability,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)


class ContainerHealthyCapability(TransactionCapability):
    """Repair and validate the prerequisites of an existing container."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_healthy"
        ),
        version="1.0.0",
        name="Healthy Container",
        description=(
            "Ensure that an existing container has valid local metadata and "
            "a synchronized storage index entry."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "health"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HEALTHY.description(lang)

    def is_satisfied(self, context: CliContextPort) -> bool:
        try:
            container_path = Path(
                str(context.get_parameter_value("container_path") or "")
            ).expanduser().resolve()
            root_path = Path(context.root_path).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return False

        if not container_path.is_dir():
            return False

        return (
            check_container_metadata_ready(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            == 0
            and check_container_storage_index_ready(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            == 0
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        from ontobdc.storage.plugin.capability.transformation.container_metadata_ready import (
            ContainerMetadataReadyCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_storage_index_ready import (
            ContainerStorageIndexReadyCapability,
        )

        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        if not container_path.is_dir():
            raise ValueError(
                f"Container path is not an accessible directory: {container_path}"
            )

        metadata_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerMetadataReadyCapability(),
            context,
        )
        storage_index_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerStorageIndexReadyCapability(),
            context,
        )

        return {
            "resulting_state": ContainerUpdateProcessState.CONTAINER_HEALTHY,
            "container_path": str(container_path),
            "reused_capabilities": {
                "container_metadata_ready": metadata_result,
                "container_storage_index_ready": storage_index_result,
            },
        }
