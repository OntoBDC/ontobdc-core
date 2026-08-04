from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import ContainerCreateProcessState
from ontobdc.storage.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)


class ContainerManifestSyncedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.storage.plugin.capability.transformation.target.container_manifest_synced",
        version="1.0.0",
        name="Container Manifest Synced",
        description="Ensure that the container RO-Crate metadata file exists and lists all container files excluding marker and dataset directories.",
        author=["TRAE"],
        tags=["storage", "container", "create", "manifest"],
        supported_languages=["en", "pt-br"],
    )

    def label(self, lang: str = "en") -> str:
        return "Container Manifest Synced"

    def description(self, lang: str = "en") -> str:
        return "Creates or updates the RO-Crate metadata file for the container with an up-to-date file inventory."

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        target_path: str = str(context.get_parameter_value("container_path")).strip()
        root_path: str = str(context.root_path).strip()
        if check_container_manifest_synced(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_manifest_synced(
                container_path=target_path,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix container manifest during storage container creation.")

        if check_container_manifest_synced(
            container_path=target_path,
            root_path=root_path,
        ) != 0:
            raise ValueError("Container manifest is still invalid after the storage container hotfix.")

        return {
            "resulting_state": ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED,
            "path": target_path,
        }
