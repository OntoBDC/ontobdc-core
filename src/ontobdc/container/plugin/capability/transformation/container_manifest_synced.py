from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_create.state import ContainerCreateProcessState
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)


class ContainerManifestSyncedCapability(TransactionCapability):
    METADATA = CapabilityMetadata(
        id="org.ontobdc.container.plugin.capability.transformation.target.container_manifest_synced",
        version="1.1.0",
        name="Container Manifest Synced",
        description=(
            "Ensure that the container RO-Crate metadata file exists, lists all "
            "container files excluding marker and dataset directories, and keeps "
            "filesystem metadata that does not require reading file content in sync."
        ),
        author=["TRAE"],
        tags=["storage", "container", "create", "manifest"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "RO-Crate manifest was synchronized with the on-disk file set and "
                    "available filesystem metadata."
                ),
            },
            "debug_entry": {
                "en": (
                    "Synchronizing the RO-Crate manifest with the on-disk "
                    "file set and available filesystem metadata."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerCreateProcessState.CONTAINER_MANIFEST_SYNCED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        container_path_str: str = str(container_path)
        root_path: str = str(context.root_path).strip()
        if check_container_manifest_synced(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            if hotfix_container_manifest_synced(
                container_path=container_path_str,
                root_path=root_path,
            ) != 0:
                raise ValueError("Failed to hotfix container manifest during storage container creation.")

        if check_container_manifest_synced(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            raise ValueError("Container manifest is still invalid after the storage container hotfix.")

        return {
            "resulting_state": ContainerRefreshProcessState.CONTAINER_DATAPACKAGE_UPDATED,
            "container_path": container_path_str,
        }
