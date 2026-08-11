from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import (
    CapabilityExecutor,
    TransactionCapability,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState
from ontobdc.storage.plugin.check.is_container_datapackage_frictionless_valid.check import (
    main as check_container_datapackage_frictionless_valid,
)
from ontobdc.storage.plugin.check.is_container_datapackage_ro_crate_synced.check import (
    main as check_container_datapackage_ro_crate_synced,
)
from ontobdc.storage.plugin.check.is_container_manifest_synced.check import (
    main as check_container_manifest_synced,
)
from ontobdc.storage.plugin.check.is_container_metadata_ready.check import (
    main as check_container_metadata_ready,
)
from ontobdc.storage.plugin.check.is_container_storage_index_ready.check import (
    main as check_container_storage_index_ready,
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
            "org.ontobdc.storage.plugin.capability.transformation.target."
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
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HEALTHY.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_HEALTHY.description(lang)

    def check(self, context: CliContextPort) -> bool:
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
        from ontobdc.storage.plugin.capability.transformation.container_datapackage_frictionless_valid import (
            ContainerDataPackageFrictionlessValidCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_datapackage_ro_crate_synced import (
            ContainerDataPackageRoCrateSyncedCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_datapackage_updated import (
            ContainerDataPackageUpdatedCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.container_manifest_synced import (
            ContainerManifestSyncedCapability,
        )
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
        datapackage_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerDataPackageUpdatedCapability(),
            context,
        )
        manifest_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerManifestSyncedCapability(),
            context,
        )
        datapackage_frictionless_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerDataPackageFrictionlessValidCapability(),
            context,
        )
        datapackage_ro_crate_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerDataPackageRoCrateSyncedCapability(),
            context,
        )

        return {
            "resulting_state": ContainerUpdateProcessState.CONTAINER_HEALTHY,
            "container_path": str(container_path),
            "reused_capabilities": {
                "container_metadata_ready": metadata_result,
                "container_storage_index_ready": storage_index_result,
                "container_datapackage_updated": datapackage_result,
                "container_manifest_synced": manifest_result,
                "container_datapackage_frictionless_valid": datapackage_frictionless_result,
                "container_datapackage_ro_crate_synced": datapackage_ro_crate_result,
            },
        }
