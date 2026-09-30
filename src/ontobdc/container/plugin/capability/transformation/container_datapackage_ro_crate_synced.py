from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    main as check_container_datapackage_ro_crate_synced,
)
from ontobdc.container.plugin.check.is_container_datapackage_ro_crate_synced.hotfix import (
    main as hotfix_container_datapackage_ro_crate_synced,
)


class ContainerDataPackageRoCrateSyncedCapability(TransactionCapability):
    """Add datapackage.json resources for frictionless-compatible RO-Crate files."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_datapackage_ro_crate_synced"
        ),
        version="1.0.0",
        name="Container Data Package RO-Crate Synced",
        description=(
            "Describe every frictionless-compatible RO-Crate file as a "
            "Data Package resource."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "datapackage", "ro-crate"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Frictionless-compatible RO-Crate files were registered as "
                    "resources in the Data Package descriptor."
                ),
            },
            "debug_entry": {
                "en": (
                    "Registering Frictionless-compatible RO-Crate files as "
                    "resources in the Data Package descriptor."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        container_path_str: str = str(container_path)
        root_path: str = str(context.root_path).strip()

        if check_container_datapackage_ro_crate_synced(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            if hotfix_container_datapackage_ro_crate_synced(
                container_path=container_path_str,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container Data Package RO-Crate sync."
                )

        if check_container_datapackage_ro_crate_synced(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package is still missing RO-Crate resources "
                "after the hotfix."
            )

        return {
            "resulting_state": (
                ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED
            ),
            "container_path": container_path_str,
        }
