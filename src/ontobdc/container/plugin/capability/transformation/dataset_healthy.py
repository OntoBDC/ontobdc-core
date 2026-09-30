from typing import Any, Dict
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_dataset_healthy.check import (
    evaluate as evaluate_dataset_healthy,
)
from ontobdc.container.plugin.check.is_dataset_facade_valid.hotfix import (
    main as hotfix_dataset_facade_valid,
)
from ontobdc.container.plugin.check.is_dataset_structure_valid.hotfix import (
    main as hotfix_dataset_structure_valid,
)
from ontobdc.container.plugin.check.is_dataset_surfaceable_synced.hotfix import (
    main as hotfix_dataset_surfaceable_synced,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.check import (
    main as check_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_metadata_ready.hotfix import (
    main as hotfix_dataset_metadata_ready,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.check import (
    main as check_dataset_container_index_ready,
)
from ontobdc.container.plugin.check.is_dataset_container_index_ready.hotfix import (
    main as hotfix_dataset_container_index_ready,
)


class DatasetHealthyCapability(TransactionCapability):
    """Repair and validate the prerequisites of an existing dataset.

    Mirrors ContainerHealthyCapability at dataset scope: directory structure,
    metadata, the parent container index, dataset facade, surfaceable marker,
    and Data Package are repaired in dependency order and then validated.
    An existing invalid facade is preserved and reported as unhealthy rather
    than overwritten.
    """

    METADATA = CapabilityMetadata(
        id=(
            "org.ontobdc.container.plugin.capability.transformation.target."
            "dataset_healthy"
        ),
        version="1.0.0",
        name="Healthy Dataset",
        description=(
            "Ensure that an existing dataset has its required structure, "
            "valid local metadata, a canonical facade, a synchronized "
            "container index entry, and an up-to-date Data Package."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["storage", "dataset", "update", "health"],
        supported_languages=["en", "pt-br"],
        log_message={
            "info": {
                "en": (
                    "Dataset structure, metadata, facade, container index entry, "
                    "and Data Package were repaired and validated."
                ),
            },
            "debug_entry": {
                "en": (
                    "Repairing and validating dataset structure, metadata, "
                    "facade, container index entry, and Data Package."
                ),
            },
        },
    )

    def label(self, lang: str = "en") -> str:
        return "Healthy Dataset"

    def description(self, lang: str = "en") -> str:
        return (
            "Repairs and validates a dataset's structure, metadata, facade, "
            "container index entry, and Data Package."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:

        dataset_path: str = RequiredParameter.of(context, "dataset_path")
        root_path: str = str(context.root_path).strip()

        hotfix_dataset_structure_valid(
            dataset_path=dataset_path,
            root_path=root_path,
        )

        metadata_ready_result: Dict[str, Any] = self._ensure_dataset_metadata_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        )
        container_index_result: Dict[str, Any] = (
            self._ensure_dataset_container_index_ready(
                dataset_path=dataset_path,
                root_path=root_path,
            )
        )

        hotfix_dataset_facade_valid(
            dataset_path=dataset_path,
            root_path=root_path,
        )
        hotfix_dataset_surfaceable_synced(
            dataset_path=dataset_path,
            root_path=root_path,
        )
        ContainerDataPackageSynchronizer().sync(
            Path(dataset_path).expanduser().resolve()
        )

        checks: Dict[str, int] = evaluate_dataset_healthy(dataset_path, root_path)
        healthy: bool = all(result == 0 for result in checks.values())

        return {
            "dataset_path": dataset_path,
            "healthy": healthy,
            "checks": checks,
            "reused_steps": {
                "dataset_metadata_ready": metadata_ready_result,
                "dataset_container_index_ready": container_index_result,
            },
        }

    @staticmethod
    def _ensure_dataset_metadata_ready(
        *,
        dataset_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_dataset_metadata_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ) != 0:
            if hotfix_dataset_metadata_ready(
                dataset_path=dataset_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix dataset metadata while repairing dataset health."
                )

        if check_dataset_metadata_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Dataset metadata is still invalid after the health hotfix."
            )
        return {
            "path": dataset_path,
            "healthy": True,
        }

    @staticmethod
    def _ensure_dataset_container_index_ready(
        *,
        dataset_path: str,
        root_path: str,
    ) -> Dict[str, Any]:
        if check_dataset_container_index_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ) != 0:
            if hotfix_dataset_container_index_ready(
                dataset_path=dataset_path,
                root_path=root_path,
            ) != 0:
                raise ValueError(
                    "Failed to hotfix dataset container index entry while "
                    "repairing dataset health."
                )

        if check_dataset_container_index_ready(
            dataset_path=dataset_path,
            root_path=root_path,
        ) != 0:
            raise ValueError(
                "Dataset container index entry is still invalid after the "
                "health hotfix."
            )
        return {
            "path": dataset_path,
            "healthy": True,
        }
