from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    main as check_container_datapackage_ro_crate_synced,
)
from ontobdc.storage.plugin.check.is_container_datapackage_ro_crate_synced.hotfix import (
    main as hotfix_container_datapackage_ro_crate_synced,
)


class ContainerDataPackageRoCrateSyncedCapability(TransactionCapability):
    """Add datapackage.json resources for frictionless-compatible RO-Crate files."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
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
    )

    def label(self, lang: str = "en") -> str:
        return "Container Data Package RO-Crate Synced"

    def description(self, lang: str = "en") -> str:
        return (
            "Adds Data Package resources for frictionless-compatible files "
            "already listed in the RO-Crate manifest."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("container_path")).strip()
        root_path: str = str(context.root_path).strip()

        if check_container_datapackage_ro_crate_synced(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_datapackage_ro_crate_synced(
                container_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container Data Package RO-Crate sync."
                )

        if check_container_datapackage_ro_crate_synced(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package is still missing RO-Crate resources "
                "after the hotfix."
            )

        return {
            "resulting_state": "container_datapackage_ro_crate_synced",
            "path": target_path,
        }
