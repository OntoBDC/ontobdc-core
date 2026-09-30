from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import StorageBootstrap
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)


class ContainerRoCrateUpdatedCapability(TransactionCapability):
    """Reuse the container manifest capability to update the RO-Crate metadata."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_ro_crate_updated"
        ),
        version="1.0.0",
        name="Updated Container RO-Crate",
        description=(
            "Synchronize and validate the container RO-Crate metadata by reusing "
            "the existing container manifest transformation."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "rocrate", "manifest"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container RO-Crate metadata was synchronized and validated "
                    "against the current manifest."
                ),
            },
            "debug_entry": {
                "en": (
                    "Synchronizing and validating the container RO-Crate "
                    "metadata against the current manifest."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:

        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        container_path_str: str = str(container_path)
        root_path_str: str = str(context.root_path).strip()

        if check_container_manifest_synced(
            container_path=container_path_str,
            root_path=root_path_str,
        ) != 0:
            if hotfix_container_manifest_synced(
                container_path=container_path_str,
                root_path=root_path_str,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container manifest while updating the "
                    "container RO-Crate."
                )

        if check_container_manifest_synced(
            container_path=container_path_str,
            root_path=root_path_str,
        ) != 0:
            raise ValueError(
                "Container manifest is still invalid after the RO-Crate update hotfix."
            )

        ro_crate_path: Path = StorageBootstrap.get_container_crate_metadata_file_path(
            container_path
        )

        return {
            "resulting_state": (
                ContainerRefreshProcessState.CONTAINER_RO_CRATE_UPDATED
            ),
            "container_path": container_path_str,
            "ro_crate_path": str(ro_crate_path),
            "manifest_synced": {
                "path": container_path_str,
                "healthy": True,
            },
        }
