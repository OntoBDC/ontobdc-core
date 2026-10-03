from typing import Any, Dict, List

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.container.plugin.check.is_dataset_healthy.check import (
    evaluate as evaluate_dataset_healthy,
)
from ontobdc.container.plugin.check.is_dataset_healthy.hotfix import (
    main as hotfix_dataset_healthy,
)

class DatasetHealthyCapability(TransactionCapability):
    """Repair and validate the prerequisites of an existing dataset.

    Mirrors ContainerHealthyCapability at dataset scope: directory structure,
    metadata, the parent container index, dataset facade, surfaceable marker,
    and Data Package are repaired in dependency order and then validated.
    An existing invalid facade is preserved, not overwritten, so it leaves
    the dataset unhealthy; a dataset still unhealthy after the repair is an
    error naming the checks it fails.
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

        hotfix_dataset_healthy(dataset_path=dataset_path, root_path=root_path)
        checks: Dict[str, int] = evaluate_dataset_healthy(dataset_path, root_path)
        failing: List[str] = sorted(name for name, result in checks.items() if result != 0)
        if failing:
            raise ValueError(
                f"Dataset {dataset_path} is unhealthy after repair; it fails "
                + ", ".join(failing)
                + "."
            )

        return {
            "dataset_path": dataset_path,
            "healthy": True,
            "checks": checks,
        }
