from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
    ContainerDataPackageSyncResult,
)
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState
from ontobdc.storage.plugin.check.is_container_datapackage_updated.check import (
    main as check_container_datapackage_updated,
)


class ContainerDataPackageUpdatedCapability(TransactionCapability):
    """Synchronize the container-level Frictionless Data Package descriptor."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "container_datapackage_updated"
        ),
        version="1.0.0",
        name="Updated Container Data Package",
        description=(
            "Synchronize the container Data Package descriptor with its current "
            "local resources while preserving enriched and external descriptors."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "datapackage"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container Data Package descriptor was synchronized with current "
                    "local resources while enriched and external descriptors were "
                    "preserved."
                ),
            },
            "debug_entry": {
                "en": (
                    "Synchronizing the container Data Package descriptor "
                    "with current local resources while preserving enriched "
                    "and external descriptors."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_DATAPACKAGE_UPDATED.label(
            lang
        )

    def description(self, lang: str = "en") -> str:
        return (
            ContainerUpdateProcessState.CONTAINER_DATAPACKAGE_UPDATED.description(
                lang
            )
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        result: ContainerDataPackageSyncResult = (
            ContainerDataPackageSynchronizer().sync(container_path)
        )

        if check_container_datapackage_updated(
            container_path=str(container_path),
            root_path=str(context.root_path),
        ) != 0:
            raise ValueError(
                "Container Data Package descriptor is still stale after synchronization."
            )

        return {
            "resulting_state": (
                ContainerUpdateProcessState.CONTAINER_DATAPACKAGE_UPDATED
            ),
            "container_path": str(container_path),
            "datapackage_path": str(result.datapackage_path),
            "resource_count": result.resource_count,
            "local_resource_count": result.local_resource_count,
            "added_resource_count": result.added_resource_count,
            "updated_resource_count": result.updated_resource_count,
            "removed_resource_count": result.removed_resource_count,
        }
