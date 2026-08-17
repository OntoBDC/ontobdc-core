from pathlib import Path
from typing import Any, Dict

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import (
    CapabilityExecutor,
    TransactionCapability,
)
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.storage.plugin.check.is_dataset_healthy.check import (
    evaluate as evaluate_dataset_healthy,
)
from ontobdc.storage.plugin.check.is_dataset_surfaceable_synced.hotfix import (
    main as hotfix_dataset_surfaceable_synced,
)


class DatasetHealthyCapability(TransactionCapability):
    """Repair and validate the prerequisites of an existing dataset.

    Mirrors ContainerHealthyCapability at dataset scope: dataset metadata,
    its entry in the parent container.ttl, its own Data Package sync and
    frictionless-validity, and its obdc:SurfaceableEntity marker (synced
    from the locally materialized linkset/type.ttl) are checked and
    hotfixed. Its facade materialization (linkset/facade.ttl) is checked
    but not repaired here: the source facade file is only known to the
    context/entity-facade resolution layer, which this storage-layer
    capability must not depend on — a broken facade is reported in the
    result, not silently ignored, but it does not raise.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.storage.plugin.capability.transformation.target."
            "dataset_healthy"
        ),
        version="1.0.0",
        name="Healthy Dataset",
        description=(
            "Ensure that an existing dataset has valid local metadata, a "
            "synchronized container index entry, and an up-to-date Data "
            "Package; report whether its facade materialization is still "
            "valid."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "update", "health"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Dataset metadata, container index entry, and Data Package were "
                    "repaired and validated; facade health was reported."
                ),
            },
            "debug_entry": {
                "en": (
                    "Repairing and validating dataset metadata, the "
                    "container index entry, and the Data Package while "
                    "checking facade health."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Healthy Dataset"

    def description(self, lang: str = "en") -> str:
        return (
            "Repairs a dataset's metadata, container index entry, and "
            "Data Package, and reports whether its facade is still valid."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        from ontobdc.storage.plugin.capability.transformation.dataset_container_index_ready import (
            DatasetContainerIndexReadyCapability,
        )
        from ontobdc.storage.plugin.capability.transformation.dataset_metadata_ready import (
            DatasetMetadataReadyCapability,
        )

        dataset_path: str = str(
            context.get_parameter_value("dataset_path") or ""
        ).strip()
        root_path: str = str(context.root_path).strip()
        if not dataset_path:
            raise ValueError("dataset_path is required to check dataset health.")

        CapabilityExecutor.execute(DatasetMetadataReadyCapability(), context)
        CapabilityExecutor.execute(DatasetContainerIndexReadyCapability(), context)
        ContainerDataPackageSynchronizer().sync(Path(dataset_path).expanduser().resolve())
        hotfix_dataset_surfaceable_synced(dataset_path=dataset_path, root_path=root_path)

        checks: Dict[str, int] = evaluate_dataset_healthy(dataset_path, root_path)
        healthy: bool = all(result == 0 for result in checks.values())

        return {
            "dataset_path": dataset_path,
            "healthy": healthy,
            "checks": checks,
        }
