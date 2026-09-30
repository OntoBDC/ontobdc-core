from pathlib import Path
from typing import Any, Dict, Optional

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.machine.container_refresh.state import ContainerRefreshProcessState
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_container_datapackage_frictionless_valid,
)
from ontobdc.container.plugin.check.is_container_datapackage_frictionless_valid.hotfix import (
    main as hotfix_container_datapackage_frictionless_valid,
)
from ontobdc.container.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    main as check_container_datapackage_ro_crate_synced,
)
from ontobdc.container.plugin.check.is_container_datapackage_ro_crate_synced.hotfix import (
    main as hotfix_container_datapackage_ro_crate_synced,
)
from ontobdc.container.plugin.check.is_container_datapackage_updated.check import (
    main as check_container_datapackage_updated,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_metadata_ready.hotfix import (
    main as hotfix_container_metadata_ready,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
)
from ontobdc.container.plugin.check.is_container_storage_index_ready.hotfix import (
    main as hotfix_container_storage_index_ready,
)
from ontobdc.storage.adapter.manifest import (
    ContainerDataPackageSynchronizer,
    ContainerDataPackageSyncResult,
)


class ContainerHealthyCapability(TransactionCapability):
    """Repair and validate the prerequisites of an existing container.

    Six sequential steps, each hotfixed in execute(): metadata ready,
    storage index ready, Data Package updated (blind file sync), RO-Crate
    manifest synced (blind file sync), Data Package pruned of non-
    frictionless-compatible resources, then Data Package filled in with
    every frictionless-compatible file the RO-Crate already lists.

    `check()` deliberately omits the Data Package "updated" check: its
    notion of correct (byte-for-byte match with a blind, format-agnostic
    sync) is superseded by — and permanently at odds with — the pruned
    Data Package the last two steps produce, which excludes non-
    frictionless files on purpose. Gating overall health on it would make a
    genuinely healthy, pruned container register as perpetually unhealthy.
    It still runs as an execute()-time refresh step (via
    ContainerDataPackageUpdatedCapability's own internal check/hotfix), just
    not as part of this class's own pass/fail gate.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "container_healthy"
        ),
        version="1.0.0",
        name="Healthy Container",
        description=(
            "Ensure that an existing container has valid local metadata, a "
            "synchronized storage index entry, an up-to-date Data Package "
            "and RO-Crate manifest, and that the Data Package only "
            "describes frictionless-compatible files already in the "
            "RO-Crate."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "container", "update", "health"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Container data directory structure, RO-Crate manifest, and "
                    "Frictionless Data Package descriptor were validated; no "
                    "integrity issues or non-compliant artifacts were found."
                ),
            },
            "debug_entry": {
                "en": (
                    "Validating the container data directory structure, "
                    "RO-Crate manifest, and Frictionless Data Package "
                    "descriptor for integrity issues and non-compliant "
                    "artifacts."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerRefreshProcessState.CONTAINER_HEALTHY.description(lang)

    def check(self, context: CliContextPort) -> bool:
        container_path_value: Optional[str] = RequiredParameter.optional(
            context,
            "container_path",
        )
        if container_path_value is None:
            return False

        try:
            container_path = Path(container_path_value).expanduser().resolve()
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
            and check_container_manifest_synced(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            == 0
            and check_container_datapackage_frictionless_valid(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            == 0
            and check_container_datapackage_ro_crate_synced(
                container_path=str(container_path),
                root_path=str(root_path),
            )
            == 0
        )

    def is_satisfied(self, context: CliContextPort) -> bool:
        return self.check(context)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:

        container_path: Path = Path(
            RequiredParameter.of(context, "container_path")
        ).expanduser().resolve()
        if not container_path.is_dir():
            raise ValueError(
                f"Container path is not an accessible directory: {container_path}"
            )
        container_path_str: str = str(container_path)
        root_path_str: str = str(context.root_path).strip()

        metadata_result: Dict[str, Any] = self._ensure_container_metadata_ready(
            container_path=container_path_str,
            root_path=root_path_str,
        )
        storage_index_result: Dict[str, Any] = (
            self._ensure_container_storage_index_ready(
                container_path=container_path_str,
                root_path=root_path_str,
            )
        )
        datapackage_result: Dict[str, Any] = (
            self._ensure_container_datapackage_updated(
                container_path=container_path,
                root_path=root_path_str,
            )
        )
        manifest_result: Dict[str, Any] = self._ensure_container_manifest_synced(
            container_path=container_path_str,
            root_path=root_path_str,
        )
        datapackage_frictionless_result: Dict[str, Any] = (
            self._ensure_container_datapackage_frictionless_valid(
                container_path=container_path_str,
                root_path=root_path_str,
            )
        )
        datapackage_ro_crate_result: Dict[str, Any] = (
            self._ensure_container_datapackage_ro_crate_synced(
                container_path=container_path_str,
                root_path=root_path_str,
            )
        )

        return {
            "resulting_state": ContainerRefreshProcessState.CONTAINER_HEALTHY,
            "container_path": str(container_path),
            "reused_steps": {
                "container_metadata_ready": metadata_result,
                "container_storage_index_ready": storage_index_result,
                "container_datapackage_updated": datapackage_result,
                "container_manifest_synced": manifest_result,
                "container_datapackage_frictionless_valid": datapackage_frictionless_result,
                "container_datapackage_ro_crate_synced": datapackage_ro_crate_result,
            },
        }

    @staticmethod
    def _ensure_container_metadata_ready(
        *,
        container_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_container_metadata_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_metadata_ready(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container metadata while repairing container health."
                )
        if check_container_metadata_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container metadata is still invalid after the health hotfix."
            )
        return {
            "path": container_path,
            "healthy": True,
        }

    @staticmethod
    def _ensure_container_storage_index_ready(
        *,
        container_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_container_storage_index_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_storage_index_ready(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container storage index entry while "
                    "repairing container health."
                )
        if check_container_storage_index_ready(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container storage index entry is still invalid after the "
                "health hotfix."
            )
        return {
            "path": container_path,
            "healthy": True,
        }

    @staticmethod
    def _ensure_container_datapackage_updated(
        *,
        container_path: Path,
        root_path: str,
    ) -> Dict[str, Any]:
        sync_result: ContainerDataPackageSyncResult = (
            ContainerDataPackageSynchronizer().sync(container_path)
        )
        container_path_str: str = str(container_path)
        if check_container_datapackage_updated(
            container_path=container_path_str,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package descriptor is still stale after synchronization."
            )
        return {
            "container_path": container_path_str,
            "datapackage_path": str(sync_result.datapackage_path),
            "resource_count": sync_result.resource_count,
            "local_resource_count": sync_result.local_resource_count,
            "added_resource_count": sync_result.added_resource_count,
            "updated_resource_count": sync_result.updated_resource_count,
            "removed_resource_count": sync_result.removed_resource_count,
        }

    @staticmethod
    def _ensure_container_manifest_synced(
        *,
        container_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_container_manifest_synced(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_manifest_synced(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container manifest while repairing container health."
                )
        if check_container_manifest_synced(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container manifest is still invalid after the health hotfix."
            )
        return {
            "path": container_path,
            "healthy": True,
        }

    @staticmethod
    def _ensure_container_datapackage_frictionless_valid(
        *,
        container_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_container_datapackage_frictionless_valid(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_datapackage_frictionless_valid(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container Data Package frictionless compatibility."
                )
        if check_container_datapackage_frictionless_valid(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package still has non-frictionless-compatible "
                "resources after the health hotfix."
            )
        return {
            "path": container_path,
            "healthy": True,
        }

    @staticmethod
    def _ensure_container_datapackage_ro_crate_synced(
        *,
        container_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_container_datapackage_ro_crate_synced(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            if hotfix_container_datapackage_ro_crate_synced(
                container_path=container_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix container Data Package RO-Crate sync."
                )
        if check_container_datapackage_ro_crate_synced(
            container_path=container_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Container Data Package is still missing RO-Crate resources "
                "after the health hotfix."
            )
        return {
            "path": container_path,
            "healthy": True,
        }
