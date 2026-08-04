from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import (
    CapabilityExecutor,
    TransactionCapability,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.bootstrap import (
    get_container_crate_metadata_file_path,
)
from ontobdc.storage.domain.machine.state import ContainerUpdateProcessState


class ContainerRoCrateUpdatedCapability(TransactionCapability):
    """Reuse the container manifest capability to update the RO-Crate metadata."""

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
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
    )

    def label(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        from ontobdc.storage.plugin.capability.transformation.container_manifest_synced import (
            ContainerManifestSyncedCapability,
        )

        container_path: Path = Path(
            str(context.get_parameter_value("container_path") or "")
        ).expanduser().resolve()
        reused_result: Dict[str, Any] = CapabilityExecutor.execute(
            ContainerManifestSyncedCapability(),
            context,
        )
        ro_crate_path: Path = get_container_crate_metadata_file_path(
            container_path
        )

        return {
            "resulting_state": (
                ContainerUpdateProcessState.CONTAINER_RO_CRATE_UPDATED
            ),
            "container_path": str(container_path),
            "ro_crate_path": str(ro_crate_path),
            "reused_capability": reused_result,
        }
